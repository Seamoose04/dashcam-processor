# main.py
from __future__ import annotations

import os
import cv2
import time
from multiprocessing import Manager

from pipeline import frame_store
from pipeline.task import Task, TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline.storage import SQLiteStorage
from pipeline.scheduler import SchedulerProcess
from pipeline.dispatcher import DispatcherProcess

# Workers
from pipeline.workers.cpu_worker_mp import CPUWorkerProcess
from pipeline.workers.gpu_worker import GPUWorkerProcess

# Processors (mapping categories → functions)
from pipeline.processors.yolo_vehicle import load_vehicle_model, process_vehicle
from pipeline.processors.yolo_plate import load_plate_model, process_plate
from pipeline.processors.ocr import load_ocr, process_ocr
from pipeline.processors.plate_smooth import load_plate_smoother, process_plate_smooth
from pipeline.processors.summary import load_summary, process_summary

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

# ==========================================================================================
# MAIN PIPELINE DRIVER
# ==========================================================================================

def enqueue_video_frames(video_path: str, queue: CentralTaskQueue, db: SQLiteStorage):
    """
    Push each frame of a video into VEHICLE_DETECT tasks.
    """

    video_id = os.path.splitext(os.path.basename(video_path))[0]
    log.info(f"[MAIN] Processing video: {video_id}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log.warning(f"[MAIN] Failed to open {video_path}")
        return

    frame_idx = 0

    while True and frame_idx < 50:
        ret, frame = cap.read()
        if not ret:
            break

        # ---------------------
        # Save frame to FrameStore
        # ---------------------
        payload_ref = frame_store.save_frame(video_id, frame_idx, frame)

        # ---------------------
        # Create VEHICLE_DETECT task
        # ---------------------
        task = Task(
            category=TaskCategory.VEHICLE_DETECT,
            payload=frame,               # immediate GPU processing
            priority=0,
            video_id=video_id,
            frame_idx=frame_idx,
            meta={
                "payload_ref": payload_ref,
                "dependencies": [payload_ref]
            },
        )

        task_id = db.save_task(task)
        queue.push(task_id, task)

        frame_idx += 1

    cap.release()
    log.info(f"[MAIN] Finished enqueueing {frame_idx} frames for {video_id}")


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
    # WORKER CATEGORY ASSIGNMENTS
    # ===========================================================

    gpu_categories = [
        TaskCategory.VEHICLE_DETECT,
        TaskCategory.PLATE_DETECT,
        TaskCategory.OCR
    ]

    cpu_categories = [
        TaskCategory.PLATE_SMOOTH,
        TaskCategory.SUMMARY
    ]

    # -----------------------------------------------------------
    # GPU resource loaders / processors
    # -----------------------------------------------------------
    gpu_resource_loaders = {
        TaskCategory.OCR:          load_ocr,
        TaskCategory.VEHICLE_DETECT: load_vehicle_model,
        TaskCategory.PLATE_DETECT:   load_plate_model,
    }

    gpu_processors = {
        TaskCategory.OCR:          process_ocr,
        TaskCategory.VEHICLE_DETECT: process_vehicle,
        TaskCategory.PLATE_DETECT:   process_plate,
    }

    # -----------------------------------------------------------
    # CPU resource loaders / processors
    # -----------------------------------------------------------
    cpu_resource_loaders = {
        TaskCategory.PLATE_SMOOTH: load_plate_smoother,
        TaskCategory.SUMMARY:      load_summary,
    }

    cpu_processors = {
        TaskCategory.PLATE_SMOOTH: process_plate_smooth,
        TaskCategory.SUMMARY:      process_summary,
    }

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

    for v in videos:
        enqueue_video_frames(v, queue, db)

    # ===========================================================
    # START WORKERS
    # ===========================================================

    # GPU worker (1 for now)
    gpu_workers = []
    for wid in range(12):
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
    for wid in range(24):
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
