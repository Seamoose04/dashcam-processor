# pipeline/workers_cpu.py
from __future__ import annotations

import time
from typing import Callable, Dict, Optional, Any

from ..task import Task, TaskCategory
from ..queues import CentralTaskQueue
from ..tasks.fake_task import heavy_cpu_operation


class CPUWorker:
    """
    CPU worker that:
    - Chooses the busiest category
    - Loads a resource only when category switches
    - Drains all tasks from that category
    """

    def __init__(
        self,
        task_queue: CentralTaskQueue,
        save_result_fn: Callable[[Task, Any], None],
        resource_loaders: Dict[TaskCategory, Callable[[], Any]],
        processors: Dict[TaskCategory, Callable[[Task, Any], Any]],
        name: str = "CPUWorker"
    ):
        self.task_queue = task_queue
        self.resource_loaders = resource_loaders
        self.processors = processors
        self.save_result_fn = save_result_fn
        self.name = name

        self.current_category: Optional[TaskCategory] = None
        self.resource = None

    def debug(self, msg: str):
        print(f"[{self.name}] {msg}")

    def run_once(self):
        """Perform one scheduling step."""
        cat = self.task_queue.busiest_category()
        if cat is None:
            time.sleep(0.01)
            return

        if cat != self.current_category:
            # unload old resource
            self.current_category = cat
            self.debug(f"Switching to category: {cat.value}")
            self.resource = self.resource_loaders.get(cat, lambda: None)()

        task = self.task_queue.pop(cat)
        if task is None:
            return

        # process the task
        result = self.processors[cat](task, self.resource)

        # save the result (to sqlite or any DB handler)
        self.save_result_fn(task, result)

    def run_forever(self):
        self.debug("Worker started")
        while True:
            self.run_once()
