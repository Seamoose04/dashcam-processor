# pipeline/scheduler.py
from __future__ import annotations

import os
import time
from multiprocessing import Process
from typing import Any
import signal

from pipeline.queues import CentralTaskQueue
from pipeline.task import TaskCategory

from pipeline.shutdown import terminate
from pipeline.logger import get_logger

class SchedulerProcess(Process):
    """
    Simple scheduler/monitor process.

    Responsibilities:
    - Periodically inspect queue backlog per category
    - Read worker_status (shared Manager().dict())
    - Print a live dashboard to the terminal

    In the future, this could:
    - Adjust priorities
    - Throttle categories
    - Trigger shutdowns or scaling decisions
    """

    def __init__(
        self,
        task_queue: CentralTaskQueue,
        worker_status: Any,             # Manager().dict()
        interval: float = 1.0,
        db_path: str = "pipeline.db",
        name: str = "Scheduler",
    ):
        super().__init__()
        self.task_queue = task_queue
        self.worker_status = worker_status
        self.interval = interval
        self.name = name
        self.db_path = db_path
        self.log = get_logger(self.name)

    def _clear_screen(self) -> None:
        # Should work on most terminals; if not, you can swap to print many newlines.
        os.system("clear")

    def run(self) -> None:
        # Ignore Ctrl+C in this process; main coordinates shutdown via events.
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        # Local DB connection for backlog counts (queued + running)
        from pipeline.storage import SQLiteStorage
        db = SQLiteStorage(self.db_path)

        while not terminate.is_set():
            try:
                active_counts = db.count_tasks_by_category()
                total_active = sum(active_counts.values())
                queue_snapshot = self.task_queue.snapshot()

                self._clear_screen()
                print(f"[{self.name}] Queue and Worker Status")
                print("=" * 50)
                result_backlog = db.count_unhandled_results_by_category()
                total_results = sum(result_backlog.values())

                print(f"Active (queued+running) tasks: {total_active}")
                print(f"Undispatched results: {total_results}")
                print(f"In-queue counts (may be 0 while workers run): {queue_snapshot}")
                # In-flight workers by category (derived from heartbeats)
                inflight = {}
                for status in self.worker_status.values():
                    cat_val = status.get("category")
                    if cat_val:
                        inflight[cat_val] = inflight.get(cat_val, 0) + 1
                print(f"Workers active by category: {inflight}")
                print("\nPer-category backlog:")
                self.log.info(
                    "[HUD] active_total=%s active_by_cat=%s result_backlog=%s queue_snapshot=%s inflight=%s",
                    total_active,
                    active_counts,
                    result_backlog,
                    queue_snapshot,
                    inflight,
                )

                # Ensure stable order
                for cat in TaskCategory:
                    count = active_counts.get(cat, 0)
                    print(f"  {cat.value:15s} : {count}")

                print("\nWorkers:")
                if not self.worker_status:
                    print("  (no workers registered)")
                else:
                    now = time.time()
                    for wid, status in self.worker_status.items():
                        cat_val = status.get("category")
                        last = status.get("last_heartbeat", 0.0)
                        age = now - last if last else float("inf")
                        print(
                            f"  Worker {wid:2d} "
                            f"pid={status.get('pid')} "
                            f"cat={cat_val or 'idle':15s} "
                            f"last_heartbeat={age:5.2f}s ago"
                        )

                print("\nPress Ctrl+C in main process to stop.")
                time.sleep(self.interval)
            except Exception as e:
                self.log.exception(f"Scheduler error: {e}")
