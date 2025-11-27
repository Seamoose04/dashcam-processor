# pipeline/scheduler.py
from __future__ import annotations

import os
import time
import signal
from multiprocessing import Process
from typing import Any

from pipeline.queues import CentralTaskQueue
from pipeline.task import TaskCategory
from pipeline.shutdown import terminate
from pipeline.logger import get_logger


class SchedulerProcess(Process):
    """
    Lightweight HUD that prints queue/backpressure and worker status to stdout.
    """
    def __init__(
        self,
        task_queue: CentralTaskQueue,
        worker_status: Any,             # Manager().dict()
        interval: float = 1.0,
        name: str = "Scheduler",
    ):
        super().__init__(name=name)
        self.task_queue = task_queue
        self.worker_status = worker_status
        self.interval = interval
        self.log = get_logger(self.name)

    def _clear_screen(self) -> None:
        os.system("clear")

    def run(self) -> None:
        # Ignore Ctrl+C in this process; main coordinates shutdown via events.
        signal.signal(signal.SIGINT, signal.SIG_IGN)

        while not terminate.is_set():
            try:
                queue_snapshot = self.task_queue.snapshot()
                total_active = sum(queue_snapshot.values())

                inflight = {}
                for status in self.worker_status.values():
                    cat_val = status.get("category")
                    if cat_val:
                        inflight[cat_val] = inflight.get(cat_val, 0) + 1

                backed_up = self.task_queue.backed_up_categories()

                self._clear_screen()
                print(f"[{self.name}] Queue and Worker Status")
                print("=" * 50)
                print(f"Active tasks (queued): {total_active}")
                print(f"Backed-up categories (soft limit hit): {sorted([c.value for c in backed_up])}")
                print(f"Workers active by category: {inflight}")
                print("\nPer-category backlog:")
                for cat in TaskCategory:
                    count = queue_snapshot.get(cat, 0)
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

