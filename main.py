# main.py
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import os
import cv2
import time
from multiprocessing import Manager
import threading

from pipeline import frame_store
from pipeline.task import Task, TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline.storage import SQLiteStorage
from pipeline.scheduler import SchedulerProcess
from pipeline.dispatcher import DispatcherProcess
from pipeline.video_reader import VideoReader

from pipeline.categories import *

# Dispatcher handlers
from pipeline.dispatch_handlers import (
    handle_vehicle_detect_result,
    handle_plate_detect_result,
    handle_ocr_result,
    handle_plate_smooth_result,
)

# Logger
from pipeline.logger import get_logger
log = get_logger("main")

NUM_GPU_WORKERS=int(os.environ.get("NUM_GPU_WORKERS", 2))
NUM_CPU_WORKERS=int(os.environ.get("NUM_CPU_WORKERS", 4))

MAX_GPU_BACKLOG=int(os.environ.get("MAX_GPU_BACKLOG", 8))
MAX_CPU_BACKLOG=int(os.environ.get("MAX_CPU_BACKLOG", 16))

def main():
    # ===========================================================
    # INIT
    # ===========================================================

    INPUT_DIR = "inputs"
    DB_PATH = "pipeline.db"

    # remove old DB for a clean run
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    # init FrameStore
    frame_store.init("frame_store")

    # shared pipeline components
    queue = CentralTaskQueue()
    db = SQLiteStorage(DB_PATH)
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
        VideoReader(v, queue, db, cpu_backlog_limit=MAX_CPU_BACKLOG, gpu_backlog_limit=MAX_GPU_BACKLOG)
        for v in videos
    ]

    threads = []
    for r in readers:
        t = threading.Thread(target=r.run, daemon=True)
        t.start()
        threads.append(t)

    # ===========================================================
    # START WORKERS
    # ===========================================================

    # GPU worker (1 for now)
    gpu_workers = []
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
    cpu_workers = []
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
    # START DISPATCHER (downstream task generation)
    # ===========================================================

    handlers = {
        TaskCategory.VEHICLE_DETECT: handle_vehicle_detect_result,
        TaskCategory.PLATE_DETECT:   handle_plate_detect_result,
        TaskCategory.OCR:            handle_ocr_result,
        TaskCategory.PLATE_SMOOTH:   handle_plate_smooth_result,
    }

    dispatcher = DispatcherProcess(
        db_path=DB_PATH,
        task_queue=queue,
        handlers=handlers,
        interval=0.2,
    )
    dispatcher.start()

    # ===========================================================
    # START SCHEDULER HUD
    # ===========================================================

    scheduler = SchedulerProcess(
        task_queue=queue,
        worker_status=worker_status,
        interval=1.0
    )
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

    # ===========================================================
    # CLEAN SHUTDOWN
    # ===========================================================

    log.info("[MAIN] Shutting down...")

    for w in gpu_workers:
        w.terminate()
    for w in cpu_workers:
        w.terminate()

    dispatcher.terminate()
    scheduler.terminate()

    for w in gpu_workers:
        w.join()
    for w in cpu_workers:
        w.join()

    dispatcher.join()
    scheduler.join()

    log.info("[MAIN] All done!")


if __name__ == "__main__":
    main()
