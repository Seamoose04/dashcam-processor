# main.py
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import os
import cv2
import time
from multiprocessing import Manager
from queue import Queue as ThreadQueue, Empty
import threading

import signal
from pipeline.shutdown import stop, terminate

from pipeline import frame_store
from pipeline.task import TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline.video_reader import VideoReader
from pipeline.scheduler import SchedulerProcess

from pipeline.workers.cpu_worker_mp import CPUWorkerProcess
from pipeline.workers.gpu_worker import GPUWorkerProcess

from pipeline.categories import *

# Dispatcher handlers
from pipeline.dispatch_handlers import (
    handle_vehicle_detect_result,
    handle_vehicle_track_result,
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
NUM_VIDEO_READERS=int(os.environ.get("NUM_VIDEO_READERS", 2))

MAX_GPU_BACKLOG=int(os.environ.get("MAX_GPU_BACKLOG", 8))
MAX_CPU_BACKLOG=int(os.environ.get("MAX_CPU_BACKLOG", 16))
QUEUE_SOFT_LIMIT=int(os.environ.get("QUEUE_SOFT_LIMIT", 64))
QUEUE_HARD_LIMIT=int(os.environ.get("QUEUE_HARD_LIMIT", 128))

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
    TaskCategory.VEHICLE_TRACK:   handle_vehicle_track_result,
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

    log.info(
        "[CONFIG] gpu_workers=%s cpu_workers=%s gpu_backlog_limit=%s cpu_backlog_limit=%s",
        NUM_GPU_WORKERS,
        NUM_CPU_WORKERS,
        MAX_GPU_BACKLOG,
        MAX_CPU_BACKLOG,
    )
    log.info("[CONFIG] video_readers=%s", NUM_VIDEO_READERS)

    manager = Manager()
    worker_status = manager.dict()
    frame_refcounts = manager.dict()
    frame_lock = manager.Lock()

    # init FrameStore with shared refcounts
    frame_store.init("frame_store", refcounts=frame_refcounts, lock=frame_lock)

    # shared pipeline components
    queue = CentralTaskQueue(
        soft_limits={cat: QUEUE_SOFT_LIMIT for cat in TaskCategory},
        hard_limits={cat: QUEUE_HARD_LIMIT for cat in TaskCategory},
    )
    global _QUEUE_REF
    _QUEUE_REF = queue
    scheduler = SchedulerProcess(task_queue=queue, worker_status=worker_status, interval=1.0)

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

    video_queue: ThreadQueue[str] = ThreadQueue()
    for v in videos:
        video_queue.put(v)

    threads = []
    gpu_workers = []
    cpu_workers = []

    try:
        # ===========================================================
        # START VIDEO READERS
        # ===========================================================
        scheduler.start()

        def reader_worker(reader_idx: int):
            while not stop.is_set():
                try:
                    video_path = video_queue.get_nowait()
                except Empty:
                    break

                log.info("[Reader-%s] Starting %s", reader_idx, video_path)
                try:
                    reader = VideoReader(
                        video_path,
                        queue,
                        cpu_backlog_limit=MAX_CPU_BACKLOG,
                        gpu_backlog_limit=MAX_GPU_BACKLOG,
                    )
                    reader.run()
                except Exception:
                    log.exception("[Reader-%s] Error while processing %s", reader_idx, video_path)
                finally:
                    video_queue.task_done()

            log.info("[Reader-%s] Exiting (stop=%s, remaining=%s)", reader_idx, stop.is_set(), video_queue.qsize())

        num_reader_threads = min(NUM_VIDEO_READERS, len(videos))
        log.info("[MAIN] Launching %s video reader threads for %s videos", num_reader_threads, len(videos))
        for idx in range(num_reader_threads):
            t = threading.Thread(target=reader_worker, args=(idx,), daemon=True)
            t.start()
            threads.append(t)

        # ===========================================================
        # START WORKERS
        # ===========================================================

        # GPU workers
        for wid in range(NUM_GPU_WORKERS):
            w = GPUWorkerProcess(
                worker_id=0 + wid,
                task_queue=queue,
                gpu_categories=gpu_categories,
                resource_loaders=gpu_resource_loaders,
                processors=gpu_processors,
                handlers=handlers,
                worker_status=worker_status,
            )
            w.start()
            gpu_workers.append(w)

        # CPU workers
        for wid in range(NUM_CPU_WORKERS):
            w = CPUWorkerProcess(
                worker_id=100 + wid,
                task_queue=queue,
                cpu_categories=cpu_categories,
                resource_loaders=cpu_resource_loaders,
                processors=cpu_processors,
                handlers=handlers,
                worker_status=worker_status,
            )
            w.start()
            cpu_workers.append(w)

        # ===========================================================
        # WAIT UNTIL ALL TASKS ARE DONE
        # ===========================================================

        log.info("[MAIN] Waiting for pipeline to finish...")

        while True:
            time.sleep(3)

            if stop.is_set():
                log.info("[MAIN] Stop flag set; breaking wait loop to shutdown.")
                break

            total = queue.total_backlog()
            active = any(ws.get("category") for ws in worker_status.values())
            readers_active = any(t.is_alive() for t in threads)

            if total == 0 and not active and not readers_active:
                log.info("[MAIN] Pipeline complete: no backlog, workers idle, readers finished.")
                break

    except KeyboardInterrupt:
        handle_sigint(None, None)

    finally:
        # ===========================================================
        # PHASE 1 — Stop producers (readers)
        # ===========================================================
        stop.set()
        log.info("[MAIN] Stop requested. Waiting for backlog to drain...")
        for t in threads:
            t.join(timeout=2)

        # PHASE 2 — Wait for all queued work to be processed (with timeout)
        start_wait = time.monotonic()
        while True:
            backlog = queue.total_backlog()
            active = any(ws.get("category") for ws in worker_status.values())

            if backlog == 0 and not active:
                log.info("[MAIN] Backlog drained & no active workers.")
                break

            if (time.monotonic() - start_wait) > 60:
                log.warning("[MAIN] Backlog drain timeout; forcing terminate.")
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

        scheduler.terminate()
        scheduler.join(timeout=2)

        queue.shutdown()
        log.info("[MAIN] Shutdown complete.")

if __name__ == "__main__":
    main()
