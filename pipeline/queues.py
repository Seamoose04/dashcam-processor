# pipeline/queues.py
from __future__ import annotations

from multiprocessing import Manager, Lock, Queue
from multiprocessing.queues import Queue as MPQueue
from queue import Empty, Full
from typing import Optional, Iterable, Tuple, Dict, Set

from pipeline.task import Task, TaskCategory
from pipeline.categories import gpu_categories, cpu_categories

class CentralTaskQueue:
    """
    Multiprocessing-capable queue storing (task_id, Task) pairs.
    Uses per-category multiprocessing.Queue plus shared counters for backlog tracking.
    """

    def __init__(
        self,
        categories: Iterable[TaskCategory] | None = None,
        *,
        soft_limits: Dict[TaskCategory, int] | None = None,
        hard_limits: Dict[TaskCategory, int] | None = None,
        recover_ratio: float = 0.8,
    ):
        if categories is None:
            categories = list(TaskCategory)

        self._manager = Manager()
        self._queues: Dict[TaskCategory, MPQueue] = {}
        self._counts: Dict[TaskCategory, int] = self._manager.dict({cat: 0 for cat in categories})
        self._lock = Lock()
        self._soft_limits: Dict[TaskCategory, Optional[int]] = {cat: None for cat in categories}
        self._hard_limits: Dict[TaskCategory, Optional[int]] = {cat: None for cat in categories}
        # Use a managed dict as a pseudo-set: cat -> True
        self._backed_up = self._manager.dict({cat: False for cat in categories})
        self._recover_ratio = recover_ratio

        if soft_limits:
            for cat, limit in soft_limits.items():
                if cat in self._soft_limits:
                    self._soft_limits[cat] = limit
        if hard_limits:
            for cat, limit in hard_limits.items():
                if cat in self._hard_limits:
                    self._hard_limits[cat] = limit

        for cat in categories:
            maxsize = self._hard_limits.get(cat) or 0  # 0 means infinite
            self._queues[cat] = Queue(maxsize=maxsize)

    def shutdown(self) -> None:
        """Cleanly stop the backing manager process."""
        self._manager.shutdown()

    def _update_flags(self, category: TaskCategory) -> None:
        """Update backed-up flags based on soft limits and recovery ratio."""
        soft = self._soft_limits.get(category)
        if soft is None:
            return

        qlen = self._counts.get(category, 0)
        if qlen >= soft:
            self._backed_up[category] = True
        elif qlen <= int(soft * self._recover_ratio):
            self._backed_up[category] = False

    # ---------------- BASIC OPS ----------------

    def push(self, task_id: int, task: Task) -> bool:
        """
        Add a (task_id, task) pair to its category queue.
        Returns False if the hard limit is reached and the task was not enqueued.
        """
        with self._lock:
            hard = self._hard_limits.get(task.category)
            soft = self._soft_limits.get(task.category)
            count = self._counts.get(task.category, 0)

            if hard is not None and count >= hard:
                self._backed_up[task.category] = True
                return False

            try:
                self._queues[task.category].put_nowait((task_id, task))
                self._counts[task.category] = count + 1
                if soft is not None and self._counts[task.category] >= soft:
                    self._backed_up[task.category] = True
                return True
            except Full:
                self._backed_up[task.category] = True
                return False

    def pop(self, category: TaskCategory) -> Tuple[Optional[Task], Optional[int]]:
        """Return (task, task_id), or (None, None) if the queue is empty."""
        with self._lock:
            try:
                task_id, task = self._queues[category].get_nowait()
            except Empty:
                return None, None

            current = self._counts.get(category, 0)
            self._counts[category] = max(0, current - 1)
            self._update_flags(category)
            return task, task_id

    def backlog(self, category: TaskCategory) -> int:
        with self._lock:
            return self._counts.get(category, 0)

    def total_backlog(self) -> int:
        with self._lock:
            return sum(self._counts.values())

    def categories(self):
        return list(self._queues.keys())

    def busiest_category(self) -> Optional[TaskCategory]:
        """Return the category with the most tasks."""
        with self._lock:
            if all(cnt == 0 for cnt in self._counts.values()):
                return None
            return max(self._counts, key=lambda c: self._counts[c])

    def snapshot(self):
        """Return {category: backlog_count} for monitoring."""
        with self._lock:
            return {cat: self._counts.get(cat, 0) for cat in self._queues.keys()}

    def total_gpu_backlog(self):
        return sum(self.backlog(cat) for cat in gpu_categories)

    def total_cpu_backlog(self):
        return sum(self.backlog(cat) for cat in cpu_categories)

    # ---------------- Backpressure helpers ----------------

    def is_backed_up(self, category: TaskCategory) -> bool:
        with self._lock:
            return bool(self._backed_up.get(category))

    def backed_up_categories(self) -> Set[TaskCategory]:
        with self._lock:
            return {cat for cat, flag in self._backed_up.items() if flag}
