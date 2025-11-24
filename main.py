# main.py
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import os
import cv2
import time
from multiprocessing import Manager
import threading

import signal
from pipeline.shutdown import stop, terminate

from pipeline import frame_store
from pipeline.task import TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline.storage import SQLiteStorage
from pipeline.scheduler import SchedulerProcess
from pipeline.dispatcher import DispatcherProcess
from pipeline.video_reader import VideoReader

from pipeline.workers.cpu_worker_mp import CPUWorkerProcess
from pipeline.workers.gpu_worker import GPUWorkerProcess

from pipeline.categories import *

# Dispatcher handlers
from pipeline.dispatch_handlers import (
    handle_vehicle_detect_result,
    handle_plate_detect_result,
    handle_ocr_result,
    handle_plate_smooth_result,
    handle_final_write_result,
)

# Logger
from pipeline.logger import get_logger
log = get_logger("main")

NUM_GPU_WORKERS=int(os.environ.get("NUM_GPU_WORKERS", 2))
NUM_CPU_WORKERS=int(os.environ.get("NUM_CPU_WORKERS", 4))
NUM_DISPATCHERS=int(os.environ.get("NUM_DISPATCHERS", 1))
DISPATCH_FETCH_LIMIT=int(os.environ.get("DISPATCH_FETCH_LIMIT", 32))

MAX_GPU_BACKLOG=int(os.environ.get("MAX_GPU_BACKLOG", 8))
MAX_CPU_BACKLOG=int(os.environ.get("MAX_CPU_BACKLOG", 16))

_QUEUE_REF: CentralTaskQueue | None = None  # set once queue is created so SIGINT handler can log it

def handle_sigint(signum, frame):
    log.info("\n[MAIN] Stop requested... finishing queued items...")
    # Snapshot backlog at the exact moment Ctrl+C arrives to debug sudden queue spikes.
    if _QUEUE_REF is not None:
        snap = _QUEUE_REF.snapshot()
        total = sum(snap.values())
        log.info("[MAIN] Backlog snapshot on SIGINT: total=%s %s", total, snap)
    stop.set()

signal.signal(signal.SIGINT, handle_sigint)
signal.signal(signal.SIGTERM, handle_sigint)

handlers = {
    TaskCategory.VEHICLE_DETECT: handle_vehicle_detect_result,
    TaskCategory.PLATE_DETECT:   handle_plate_detect_result,
    TaskCategory.OCR:            handle_ocr_result,
    TaskCategory.PLATE_SMOOTH:   handle_plate_smooth_result,
    TaskCategory.FINAL_WRITE:    handle_final_write_result,
}

def main():
    # ===========================================================
    # INIT
    # ===========================================================

    INPUT_DIR = "inputs"
    DB_PATH = "pipeline.db"

    log.info(
        "[CONFIG] gpu_workers=%s cpu_workers=%s gpu_backlog_limit=%s cpu_backlog_limit=%s",
        NUM_GPU_WORKERS,
        NUM_CPU_WORKERS,
        MAX_GPU_BACKLOG,
        MAX_CPU_BACKLOG,
    )

    # remove old DB for a clean run
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # init FrameStore
    frame_store.init("frame_store")

    # shared pipeline components
    queue = CentralTaskQueue()
    global _QUEUE_REF
    _QUEUE_REF = queue
    manager = Manager()
    worker_status = manager.dict()

    # ===========================================================
    # ENQUEUE ALL VIDEOS IN `inputs/`
    # ===========================================================

    videos = [
        os.path.join(INPUT_DIR, f)
        for f in os.listdir(INPUT_DIR)
        if f.lower().endswith((".mp4", ".mov", ".avi", ".mkv"))
    ]

    if not videos:
        log.warning("[MAIN] No videos found in inputs/")
        return

    readers = [
        VideoReader(v, queue, DB_PATH, cpu_backlog_limit=MAX_CPU_BACKLOG, gpu_backlog_limit=MAX_GPU_BACKLOG)
        for v in videos
    ]

    threads = []
    gpu_workers = []
    cpu_workers = []

    scheduler = SchedulerProcess(
        task_queue=queue,
        worker_status=worker_status,
        interval=1.0,
        db_path=DB_PATH,
    )
    dispatchers = [
        DispatcherProcess(
            db_path=DB_PATH,
            task_queue=queue,
            handlers=handlers,
            interval=0.05,
            name=f"Dispatcher-{i}",
            fetch_limit=DISPATCH_FETCH_LIMIT,
        )
        for i in range(NUM_DISPATCHERS)
    ]

    try:
        # ===========================================================
        # START VIDEO READERS
        # ===========================================================
        for r in readers:
            t = threading.Thread(target=r.run, daemon=True)
            t.start()
            threads.append(t)

        # ===========================================================
        # START WORKERS
        # ===========================================================

        # GPU worker (1 for now)
        for wid in range(NUM_GPU_WORKERS):
            w = GPUWorkerProcess(
                worker_id=0 + wid,
                task_queue=queue,
                db_path=DB_PATH,
                gpu_categories=gpu_categories,
                resource_loaders=gpu_resource_loaders,
                processors=gpu_processors,
                worker_status=worker_status,
            )
            w.start()
            gpu_workers.append(w)

        # CPU workers (2 recommended)
        for wid in range(NUM_CPU_WORKERS):
            w = CPUWorkerProcess(
                worker_id=100 + wid,
                task_queue=queue,
                db_path=DB_PATH,
                cpu_categories=cpu_categories,
                resource_loaders=cpu_resource_loaders,
                processors=cpu_processors,
                worker_status=worker_status,
            )
            w.start()
            cpu_workers.append(w)

        # ===========================================================
        # START SCHEDULER HUD
        # ===========================================================

        for d in dispatchers:
            d.start()
        scheduler.start()

        # ===========================================================
        # WAIT UNTIL ALL TASKS ARE DONE
        # ===========================================================

        log.info("[MAIN] Waiting for pipeline to finish...")

        while True:
            time.sleep(3)

            total = queue.total_backlog()
            active = any(ws.get("category") for ws in worker_status.values())

            if total == 0 and not active:
                log.info("[MAIN] Pipeline complete: no backlog & workers idle.")
                break

    except KeyboardInterrupt:
        handle_sigint(None, None)

    finally:
        # ===========================================================
        # PHASE 1 — Stop producers (readers)
        # ===========================================================
        stop.set()
        log.info("[MAIN] Stop requested. Waiting for backlog to drain...")

        # PHASE 2 — Wait for all queued work to be processed
        while True:
            backlog = queue.total_backlog()
            active = any(ws.get("category") for ws in worker_status.values())

            if backlog == 0 and not active:
                log.info("[MAIN] Backlog drained & no active workers.")
                break

            time.sleep(1)

        # ===========================================================
        # PHASE 3 — Tell workers to exit their loops
        # ===========================================================
        log.info("[MAIN] Terminating workers...")
        terminate.set()

        # Workers exit gracefully when they finish their current task
        for w in gpu_workers:
            w.join(timeout=5)
        for w in cpu_workers:
            w.join(timeout=5)

        # Force-terminate any stragglers so we can safely shut down the Manager
        still_running = [w for w in gpu_workers + cpu_workers if w.is_alive()]
        for w in still_running:
            log.warning(f"[MAIN] Forcing worker {w.name} to terminate")
            w.terminate()
        for w in still_running:
            w.join(timeout=2)

        for d in dispatchers:
            d.terminate()
        scheduler.terminate()
        for d in dispatchers:
            d.join(timeout=2)
        scheduler.join(timeout=2)

        queue.shutdown()
        log.info("[MAIN] Shutdown complete.")

if __name__ == "__main__":
    main()
