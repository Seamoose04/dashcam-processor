# pipeline/video_reader.py
import cv2
import time
from typing import Optional, Callable
from pipeline.queues import CentralTaskQueue
from pipeline.storage import SQLiteStorage
from pipeline.task import Task, TaskCategory
from pipeline import frame_store

from pipeline.logger import get_logger

from pipeline.shutdown import is_shutdown
from categories import gpu_categories, cpu_categories

class VideoReader:
    """
    A streaming video reader that:
      - reads frames sequentially
      - respects GPU/CPU backpressure
      - produces VEHICLE_DETECT tasks (or TRACK_ASSIGN, depending on design)
      - stores frames in frame_store
      - can be run in parallel for multiple video files
    """

    def __init__(
        self,
        video_path: str,
        queue: CentralTaskQueue,
        db: SQLiteStorage,
        *,
        gpu_backlog_limit: int = 300,
        cpu_backlog_limit: int = 300,
        sleep_interval: float = 0.02,
    ):
        self.video_path = video_path
        self.queue = queue
        self.db = db
        self.gpu_backlog_limit = gpu_backlog_limit
        self.cpu_backlog_limit = cpu_backlog_limit
        self.sleep_interval = sleep_interval

        self.cap = cv2.VideoCapture(video_path)
        self.video_id = video_path  # Or generate hash, but path is fine for now

        self.log = get_logger(f"VideoReader-{self.video_id}")

        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video: {video_path}")

    # ---------------------------------------------------------
    # Backpressure helpers
    # ---------------------------------------------------------

    def gpu_overloaded(self) -> bool:
        """Return True if GPU categories are overloaded."""
        total = sum(self.queue.backlog(cat) for cat in gpu_categories)
        return total > self.gpu_backlog_limit

    def cpu_overloaded(self) -> bool:
        """Return True if CPU categories are overloaded."""
        total = sum(self.queue.backlog(cat) for cat in cpu_categories)
        return total > self.cpu_backlog_limit

    # ---------------------------------------------------------
    # Push frame into pipeline
    # ---------------------------------------------------------

    def enqueue_frame(self, frame_idx: int, frame):
        """
        Stores frame → pushes VEHICLE_DETECT task referencing it.
        """
        # Store frame in frame_store
        payload_ref = frame_store.save_frame(self.video_id, frame_idx, frame)

        # Build vehicle detection task
        task = Task(
            category=TaskCategory.VEHICLE_DETECT,
            payload=frame,  # real image goes directly to GPU worker
            priority=0,
            video_id=self.video_id,
            frame_idx=frame_idx,
            track_id=None,
            meta={
                "payload_ref": payload_ref,
                "dependencies": [payload_ref],
            },
        )

        task_id = self.db.save_task(task)
        self.queue.push(task_id, task)

    # ---------------------------------------------------------
    # Main loop
    # ---------------------------------------------------------

    def run(self):
        """
        Reads the entire video, frame by frame.
        Applies backpressure from GPU and CPU queues.
        """
        frame_idx = 0

        while not is_shutdown():
            # Backpressure: pause if overloaded
            if self.gpu_overloaded() or self.cpu_overloaded():
                time.sleep(self.sleep_interval)
                continue

            ret, frame = self.cap.read()
            if not ret:
                break

            self.enqueue_frame(frame_idx, frame)
            frame_idx += 1

        self.cap.release()
        self.log.info(f"[VideoReader] Finished reading video: {self.video_path}")
