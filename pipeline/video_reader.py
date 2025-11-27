# pipeline/video_reader.py
import cv2
import time
import os
from typing import Optional, Callable
from pipeline.queues import CentralTaskQueue
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
        *,
        gpu_backlog_limit: int = 300,
        cpu_backlog_limit: int = 300,
        sleep_interval: float = 0.02,
    ):
        self.video_path = video_path
        self.queue = queue
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
        self._last_block_state: tuple[bool, bool] = (False, False)

    # ---------------------------------------------------------
    # Backpressure helpers
    # ---------------------------------------------------------

    def gpu_overloaded(self) -> bool:
        """Return True if GPU work exceeds limit."""
        return self.queue.total_gpu_backlog() > self.gpu_backlog_limit

    def cpu_overloaded(self) -> bool:
        """Return True if CPU work exceeds limit."""
        return self.queue.total_cpu_backlog() > self.cpu_backlog_limit

    # ---------------------------------------------------------
    # Push frame into pipeline
    # ---------------------------------------------------------

    def enqueue_frame(self, frame_idx: int, frame):
        """
        Stores frame → pushes VEHICLE_DETECT task referencing it.
        """
        # Store frame in frame_store
        payload_ref = frame_store.save_frame(self.video_id, frame_idx, frame)
        dependencies = [payload_ref]
        frame_store.add_refs(dependencies)

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
                "dependencies": dependencies,
            },
        )

        # Backpressure-aware enqueue: block if the category hits its hard limit.
        while not self.queue.push(-1, task):
            self.log.warning(
                "[Enqueue] Queue %s at hard limit — pausing before retry",
                task.category.value,
            )
            time.sleep(self.sleep_interval)

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

            state = (gpu_blocked, cpu_blocked)
            if state != self._last_block_state:
                if gpu_blocked and not self._last_block_state[0]:
                    self.log.info(
                        "[Backpressure] GPU backlog %s exceeds limit %s — pausing reads",
                        gpu_backlog,
                        self.gpu_backlog_limit,
                    )
                if not gpu_blocked and self._last_block_state[0]:
                    self.log.info(
                        "[Backpressure] GPU backlog recovered to %s/%s — resuming reads",
                        gpu_backlog,
                        self.gpu_backlog_limit,
                    )

                if cpu_blocked and not self._last_block_state[1]:
                    self.log.info(
                        "[Backpressure] CPU backlog %s exceeds limit %s — pausing reads",
                        cpu_backlog,
                        self.cpu_backlog_limit,
                    )
                if not cpu_blocked and self._last_block_state[1]:
                    self.log.info(
                        "[Backpressure] CPU backlog recovered to %s/%s — resuming reads",
                        cpu_backlog,
                        self.cpu_backlog_limit,
                    )

                # Clarify cross-state when one recovers but the other is still blocking.
                if not gpu_blocked and self._last_block_state[0] and cpu_blocked:
                    self.log.info(
                        "[Backpressure] GPU backlog recovered but CPU still blocked (%s/%s) — keeping reads paused",
                        cpu_backlog,
                        self.cpu_backlog_limit,
                    )
                if not cpu_blocked and self._last_block_state[1] and gpu_blocked:
                    self.log.info(
                        "[Backpressure] CPU backlog recovered but GPU still blocked (%s/%s) — keeping reads paused",
                        gpu_backlog,
                        self.gpu_backlog_limit,
                    )

            self._last_block_state = state

            self._gpu_blocked = gpu_blocked
            self._cpu_blocked = cpu_blocked

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
