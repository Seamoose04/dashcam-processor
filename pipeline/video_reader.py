# pipeline/video_reader.py
import cv2
import time
import os
from typing import Optional, Callable
from pipeline.queues import CentralTaskQueue
from pipeline.storage import SQLiteStorage
from pipeline.task import Task, TaskCategory
from pipeline import frame_store

from pipeline.logger import get_logger

from pipeline.shutdown import stop
from pipeline.categories import gpu_categories, cpu_categories

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
        db_path: str,
        *,
        gpu_backlog_limit: int = 300,
        cpu_backlog_limit: int = 300,
        sleep_interval: float = 0.02,
    ):
        self.video_path = video_path
        self.queue = queue
        self.db = SQLiteStorage(db_path)
        self.gpu_backlog_limit = gpu_backlog_limit
        self.cpu_backlog_limit = cpu_backlog_limit
        self.sleep_interval = sleep_interval

        self.cap = cv2.VideoCapture(video_path)
        self.video_id = os.path.splitext(os.path.basename(self.video_path))[0]  # Or generate hash, but path is fine for now

        self.log = get_logger(f"VideoReader-{self.video_id}")

        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open video: {video_path}")

        # Track when we enter/exit backpressure to avoid log spam.
        self._gpu_blocked = False
        self._cpu_blocked = False

    # ---------------------------------------------------------
    # Backpressure helpers
    # ---------------------------------------------------------

    def _active_backlog(self, categories) -> int:
        """
        Count queued + running tasks per category from SQLite.
        """
        counts = self.db.count_tasks_by_category(categories)
        return sum(counts.get(cat, 0) for cat in categories)

    def _result_backlog(self, categories) -> int:
        """
        Count unhandled results per category (work completed by a worker but not yet dispatched).
        """
        counts = self.db.count_unhandled_results_by_category(categories)
        return sum(counts.get(cat, 0) for cat in categories)

    def gpu_overloaded(self) -> bool:
        """Return True if GPU work (queued + in-flight + undispatched results) exceeds limit."""
        total = self._active_backlog(gpu_categories) + self._result_backlog(gpu_categories)
        return total > self.gpu_backlog_limit

    def cpu_overloaded(self) -> bool:
        """Return True if CPU work (queued + in-flight + undispatched results) exceeds limit."""
        total = self._active_backlog(cpu_categories) + self._result_backlog(cpu_categories)
        return total > self.cpu_backlog_limit

    def total_overloaded(self) -> bool:
        """
        Return True if combined GPU+CPU work (queued + running + undispatched results)
        exceeds the stricter of the two limits. This prevents runaway total load even
        if one side stays under its individual threshold.
        """
        gpu_total = self._active_backlog(gpu_categories) + self._result_backlog(gpu_categories)
        cpu_total = self._active_backlog(cpu_categories) + self._result_backlog(cpu_categories)
        return (gpu_total + cpu_total) > max(self.gpu_backlog_limit, self.cpu_backlog_limit)

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

        while not stop.is_set():
            # Backpressure: pause if overloaded
            gpu_backlog = self.queue.total_gpu_backlog()
            cpu_backlog = self.queue.total_cpu_backlog()

            gpu_blocked = gpu_backlog > self.gpu_backlog_limit
            cpu_blocked = cpu_backlog > self.cpu_backlog_limit
            total_blocked = self.total_overloaded()

            if gpu_blocked and not self._gpu_blocked:
                self.log.info(
                    "[Backpressure] GPU backlog %s exceeds limit %s — pausing reads",
                    gpu_backlog,
                    self.gpu_backlog_limit,
                )
            if not gpu_blocked and self._gpu_blocked:
                self.log.info(
                    "[Backpressure] GPU backlog recovered to %s/%s — resuming reads",
                    gpu_backlog,
                    self.gpu_backlog_limit,
                )
            if cpu_blocked and not self._cpu_blocked:
                self.log.info(
                    "[Backpressure] CPU backlog %s exceeds limit %s — pausing reads",
                    cpu_backlog,
                    self.cpu_backlog_limit,
                )
            if not cpu_blocked and self._cpu_blocked:
                self.log.info(
                    "[Backpressure] CPU backlog recovered to %s/%s — resuming reads",
                    cpu_backlog,
                    self.cpu_backlog_limit,
                )

            if total_blocked and not (self._gpu_blocked or self._cpu_blocked):
                self.log.info(
                    "[Backpressure] TOTAL backlog gpu=%s cpu=%s exceeds limit %s — pausing reads",
                    gpu_backlog + cpu_backlog,
                    cpu_backlog,
                    max(self.gpu_backlog_limit, self.cpu_backlog_limit),
                )
            if not total_blocked and (self._gpu_blocked or self._cpu_blocked):
                # Don't double-log if per-lane already logged resume; keep it simple.
                pass

            self._gpu_blocked = gpu_blocked or total_blocked
            self._cpu_blocked = cpu_blocked or total_blocked

            if self._gpu_blocked or self._cpu_blocked:
                time.sleep(self.sleep_interval)
                continue

            ret, frame = self.cap.read()
            if not ret:
                break

            self.enqueue_frame(frame_idx, frame)
            frame_idx += 1

        self.cap.release()
        self.log.info(f"[VideoReader] Finished reading video: {self.video_path}")
