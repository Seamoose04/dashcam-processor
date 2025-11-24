# pipeline/dispatcher.py
from __future__ import annotations

import time
from multiprocessing import Process
from typing import Any, Callable, Dict
import signal

from pipeline.task import Task, TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline.storage import SQLiteStorage
from pipeline import frame_store
from pipeline.shutdown import terminate

from pipeline.logger import get_logger

ResultHandler = Callable[[int, int, TaskCategory, Task, Any, SQLiteStorage, CentralTaskQueue], None]

class DispatcherProcess(Process):
    """
    Dispatcher process:
    - Polls SQLite for unhandled results
    - For each, looks up the originating Task + category
    - Calls a handler for that category
    - Handler can enqueue downstream tasks
    - Marks the result as handled
    """

    def __init__(
        self,
        db_path: str,
        task_queue: CentralTaskQueue,
        handlers: Dict[TaskCategory, ResultHandler],
        interval: float = 0.05,
        name: str = "Dispatcher",
        fetch_limit: int = 1024,
    ):
        super().__init__()
        self.db_path = db_path
        self.task_queue = task_queue
        self.handlers = handlers
        self.interval = interval
        self.name = name
        self.fetch_limit = fetch_limit

        self.log = get_logger(self.name)

    def _cleanup_frames_for_task(self, db: SQLiteStorage, task_id: int, task: Task) -> None:
        """
        After a task's result has been handled, check each frame in its
        dependencies list. If no other tasks (active or with unhandled
        results) depend on that frame, delete it from the frame_store.
        """
        dependencies = task.meta.get("dependencies") or []
        if not dependencies:
            return

        for payload_ref in dependencies:
            if not payload_ref:
                continue

            still_needed = db.has_other_active_or_unhandled_dependents(
                payload_ref=payload_ref,
                excluding_task_id=task_id,
            )

            if not still_needed:
                # Safe to delete
                try:
                    frame_store.delete_frame(payload_ref)
                    self.log.info(f"[DISPATCHER] Deleted frame {payload_ref} (no remaining dependents)")
                except Exception as e:
                    self.log.exception(f"[DISPATCHER] Failed to delete frame {payload_ref}: {e}")

    def run(self) -> None:
        # Keep running through Ctrl+C sent to the process group; main handles shutdown via events.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        db = SQLiteStorage(self.db_path)
        self.log.info("Dispatcher started")

        while not terminate.is_set():
            drained_any = False
            while True:
                items = db.fetch_unhandled_results(limit=self.fetch_limit)
                if not items:
                    break

                drained_any = True
                for result_id, task_id, category, task, result_obj in items:
                    handler = self.handlers.get(category)
                    if handler is not None:
                        try:
                            handler(result_id, task_id, category, task, result_obj, db, self.task_queue)
                        except Exception as e:
                            self.log.exception(f"Dispatcher handler failed on task_id={task_id}: {e}")

                    # Always mark handled to avoid infinite retries
                    db.mark_result_handled(result_id)
                    
                    try:
                        self._cleanup_frames_for_task(db, task_id, task)
                    except Exception as e:
                        self.log.exception(f"Dispatcher cleanup failed for task_id={task_id}: {e}")

            if not drained_any:
                time.sleep(self.interval)
