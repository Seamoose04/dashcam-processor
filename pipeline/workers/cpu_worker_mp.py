# pipeline/workers/cpu_worker_mp.py
from __future__ import annotations

import os
import time
import signal
from multiprocessing import Process
from typing import Callable, Dict, Optional, Any, List

from pipeline.task import Task, TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline.shutdown import terminate

from pipeline.logger import get_logger

class CPUWorkerProcess(Process):
    """
    Multiprocessing CPU worker:
    - Only handles categories listed in cpu_categories
    - Chooses the busiest CPU category
    - Loads resources per category
    - Drains tasks from that category
    - Writes results to SQLite
    - Updates worker_status for the scheduler/monitor
    """

    def __init__(
        self,
        worker_id: int,
        task_queue: CentralTaskQueue,
        cpu_categories: List[TaskCategory],
        resource_loaders: Dict[TaskCategory, Callable[[], Any]],
        processors: Dict[TaskCategory, Callable[[Task, Any], Any]],
        handlers: Dict[TaskCategory, Callable[[Task, Any, CentralTaskQueue], None]],
        worker_status: Optional[Any] = None,  # Manager().dict()
        name: Optional[str] = None,
    ):
        super().__init__()
        self.worker_id = worker_id
        self.name = name or f"CPUWorker-{worker_id}"

        self.task_queue = task_queue

        self.cpu_categories = cpu_categories
        self.resource_loaders = resource_loaders
        self.processors = processors
        self.handlers = handlers
        self.worker_status = worker_status

        self.current_category: Optional[TaskCategory] = None
        self.resource: Optional[Any] = None

        self.log = get_logger(self.name)

    def _update_status(self, category: Optional[TaskCategory]) -> None:
        if self.worker_status is None:
            return

        self.worker_status[self.worker_id] = {
            "pid": os.getpid(),
            "category": category.value if category is not None else None,
            "last_heartbeat": time.time(),
        }

    def _choose_busiest_cpu_category(self) -> Optional[TaskCategory]:
        """
        Among cpu_categories, pick the one with the largest backlog.
        """
        best_cat: Optional[TaskCategory] = None
        best_size = 0

        for cat in self.cpu_categories:
            size = self.task_queue.backlog(cat)
            if size > best_size:
                best_size = size
                best_cat = cat

        return best_cat if best_size > 0 else None

    # ------------------------ PROCESS ENTRY ------------------------

    def run(self) -> None:
        """
        Main worker loop inside a separate process.
        """
        # Ignore Ctrl+C in workers; main process coordinates shutdown via events.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        self.log.info("Worker starting (multiprocess mode)")

        while not terminate.is_set():
            cat = self._choose_busiest_cpu_category()
            self._update_status(cat)

            if cat is None:
                # No CPU categories have work right now
                time.sleep(0.05)
                continue

            # Switch resources when category changes
            if cat != self.current_category:
                self.current_category = cat
                self.log.info(f"Switching to category: {cat.value}")
                loader = self.resource_loaders.get(cat, lambda: None)
                self.resource = loader()

            task, task_id = self.task_queue.pop(cat)
            if task is None or task_id is None:
                time.sleep(0.01)
                continue

            try:
                processor = self.processors[cat]
                result = processor(task, self.resource)

                handler = self.handlers.get(cat)
                if handler is not None:
                    handler(task, result, self.task_queue)
                self.log.info(f"Completed CPU task cat={cat.value}")
            except Exception as e:
                self.log.exception(f"CPU worker error on cat={cat.value}: {e}")
            finally:
                deps = task.meta.get("dependencies") or []
                if deps:
                    from pipeline import frame_store
                    frame_store.release_refs(deps)
            self._update_status(cat)

        self.worker_status = None
        self._update_status(None)
        self.log.info("Worker terminated.")
