# pipeline/workers/gpu_worker.py
from __future__ import annotations

import os
import time
from multiprocessing import Process
from typing import Callable, Dict, List, Optional, Any

from pipeline.task import Task, TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline.storage import SQLiteStorage
from pipeline.shutdown import terminate

from pipeline.silence import silence_ultralytics, suppress_stdout
from pipeline.logger import get_logger

class GPUWorkerProcess(Process):
    """
    Multiprocessing GPU worker:

    - Handles only selected TaskCategories (e.g. VEHICLE_DETECT, PLATE_DETECT)
    - Chooses the busiest category *within* its GPU categories
    - Loads resources/models per-category (e.g. YOLO weights)
    - Processes tasks via provided processors mapping
    - Stores results in SQLite
    - Updates worker_status for the scheduler/monitor
    """

    def __init__(
        self,
        worker_id: int,
        task_queue: CentralTaskQueue,
        db_path: str,
        gpu_categories: List[TaskCategory],
        resource_loaders: Dict[TaskCategory, Callable[[], Any]],
        processors: Dict[TaskCategory, Callable[[Task, Any], Any]],
        worker_status: Optional[Any] = None,  # Manager().dict()
        name: Optional[str] = None,
    ):
        super().__init__()
        self.worker_id = worker_id
        self.name = name or f"GPUWorker-{worker_id}"

        self.task_queue = task_queue
        self.db_path = db_path

        self.gpu_categories = gpu_categories
        self.resource_loaders = resource_loaders
        self.processors = processors
        self.worker_status = worker_status

        self.current_category: Optional[TaskCategory] = None
        self.resource: Optional[Any] = None
        self.log = get_logger(self.name)

    # def debug(self, msg: str) -> None:
    #     print(f"[{self.name}] {msg}", flush=True)

    def _update_status(self, category: Optional[TaskCategory]) -> None:
        if self.worker_status is None:
            return

        self.worker_status[self.worker_id] = {
            "pid": os.getpid(),
            "category": category.value if category is not None else None,
            "last_heartbeat": time.time(),
        }

    def _choose_busiest_gpu_category(self) -> Optional[TaskCategory]:
        """
        Among gpu_categories, pick the one with the largest backlog.
        """
        best_cat: Optional[TaskCategory] = None
        best_size = 0

        for cat in self.gpu_categories:
            size = self.task_queue.backlog(cat)
            if size > best_size:
                best_size = size
                best_cat = cat

        return best_cat if best_size > 0 else None

    # ------------------------ PROCESS ENTRY ------------------------

    def run(self) -> None:
        """
        Main loop for the GPU worker process.
        Each worker opens its own SQLite connection.
        """
        self.log.info("GPU worker starting (multiprocess mode)")
        db = SQLiteStorage(self.db_path)

        silence_ultralytics()

        while not terminate.is_set():
            cat = self._choose_busiest_gpu_category()
            self._update_status(cat)

            if cat is None:
                # No GPU categories have work right now
                time.sleep(0.02)
                continue

            # Load or switch resources/models when category changes
            if cat != self.current_category:
                self.current_category = cat
                self.log.info(f"Switching to category: {cat.value}")
                loader = self.resource_loaders.get(cat, lambda: None)
                with suppress_stdout():
                    self.resource = loader()

            task, task_id = self.task_queue.pop(cat)
            if task is None or task_id is None:
                # It was empty by the time we popped; loop again
                time.sleep(0.01)
                continue

            try:
                # Process the task with the already-loaded model/resource
                processor = self.processors[cat]
                with suppress_stdout():
                    result = processor(task, self.resource)

                # Store result
                db.save_result(task_id, result)
                db.mark_task_done(task_id)
                self.log.info(f"Completed GPU task_id={task_id} cat={cat.value}")
            except Exception as e:
                self.log.exception(f"GPU worker crashed on task_id={task_id}: {e}")
                db.mark_task_done(task_id)
            self._update_status(cat)
        self.worker_status = None