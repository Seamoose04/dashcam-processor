# pipeline/queues.py
from __future__ import annotations

from multiprocessing import Manager, Lock
from typing import MutableMapping, MutableSequence, Optional, Iterable, Tuple

from pipeline.task import Task, TaskCategory
from pipeline.categories import gpu_categories, cpu_categories

class CentralTaskQueue:
    """
    Multiprocessing-capable queue storing (task_id, Task) pairs.
    Uses Manager().list() for cross-process safety.
    """

    def __init__(self, categories: Iterable[TaskCategory] | None = None):
        if categories is None:
            categories = list(TaskCategory)

        # Use MutableMapping/MutableSequence for type flexibility (ListProxy OK)
        self._manager = Manager()
        self._queues: MutableMapping[TaskCategory, MutableSequence] = {
            cat: self._manager.list() for cat in categories
        }

        self._lock = Lock()

    def shutdown(self) -> None:
        """Cleanly stop the backing manager process."""
        self._manager.shutdown()

    # ---------------- BASIC OPS ----------------

    def push(self, task_id: int, task: Task) -> None:
        """Add a (task_id, task) pair to its category queue."""
        with self._lock:
            self._queues[task.category].append((task_id, task))

    def pop(self, category: TaskCategory) -> Tuple[Optional[Task], Optional[int]]:
        """Return (task, task_id), or (None, None) if the queue is empty."""
        with self._lock:
            q = self._queues[category]
            if len(q) == 0:
                return None, None

            task_id, task = q.pop(0)
            return task, task_id

    def backlog(self, category: TaskCategory) -> int:
        with self._lock:
            return len(self._queues[category])

    def total_backlog(self) -> int:
        with self._lock:
            return sum(len(q) for q in self._queues.values())

    def categories(self):
        return list(self._queues.keys())

    def busiest_category(self) -> Optional[TaskCategory]:
        """Return the category with the most tasks."""
        with self._lock:
            if all(len(q) == 0 for q in self._queues.values()):
                return None
            return max(self._queues, key=lambda c: len(self._queues[c]))

    def snapshot(self):
        """Return {category: backlog_count} for monitoring."""
        with self._lock:
            return {cat: len(q) for cat, q in self._queues.items()}

    def total_gpu_backlog(self):
        return sum(self.backlog(cat) for cat in gpu_categories)

    def total_cpu_backlog(self):
        return sum(self.backlog(cat) for cat in cpu_categories)
