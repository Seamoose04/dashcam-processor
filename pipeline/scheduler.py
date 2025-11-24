# pipeline/scheduler.py
from __future__ import annotations

import os
import time
from multiprocessing import Process
from typing import Any

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
        name: str = "Scheduler",
    ):
        super().__init__()
        self.task_queue = task_queue
        self.worker_status = worker_status
        self.interval = interval
        self.name = name
        self.log = get_logger(self.name)

    def _clear_screen(self) -> None:
        # Should work on most terminals; if not, you can swap to print many newlines.
        os.system("clear")

    def run(self) -> None:
        while not terminate.is_set():
            try:
                snapshot = self.task_queue.snapshot()
                total = sum(snapshot.values())

                self._clear_screen()
                print(f"[{self.name}] Queue and Worker Status")
                print("=" * 50)
                print(f"Total queued tasks: {total}")
                print("\nPer-category backlog:")

                # Ensure stable order
                for cat in TaskCategory:
                    count = snapshot.get(cat, 0)
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