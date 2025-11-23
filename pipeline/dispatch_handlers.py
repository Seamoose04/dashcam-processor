# pipeline/dispatch_handlers.py
from __future__ import annotations

from typing import Any, List, Tuple

from pipeline.task import Task, TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline.storage import SQLiteStorage
from pipeline import frame_store

from pipeline.logger import get_logger
log = get_logger("dispatch_handlers")

# ------------------------------------------------------------------------
# 0. FAKE CPU (example)
# ------------------------------------------------------------------------

def handle_fake_cpu_result(
    result_id: int,
    task_id: int,
    category: TaskCategory,
    task: Task,
    result_obj: Any,
    db: SQLiteStorage,
    queue: CentralTaskQueue,
) -> None:
    log.info(
        f"[Dispatcher] FAKE_CPU_TEST handled (result_id={result_id}, task_id={task_id}) "
        f"result={result_obj}"
    )

# ------------------------------------------------------------------------
# 1. VEHICLE_DETECT → PLATE_DETECT
# ------------------------------------------------------------------------

def handle_vehicle_detect_result(
    result_id: int,
    task_id: int,
    category: TaskCategory,
    task: Task,
    result_obj: List[dict],
    db: SQLiteStorage,
    queue: CentralTaskQueue,
) -> None:
    """
    result_obj = [
        { "bbox": [x1,y1,x2,y2], "conf": 0.92 },
        ...
    ]
    """

    payload_ref = task.meta.get("payload_ref")
    video_id = task.video_id
    frame_idx = task.frame_idx

    # Dependencies from parent (or fallback to just this frame)
    dependencies = task.meta.get("dependencies") or ([payload_ref] if payload_ref else [])

    for det in result_obj:
        car_bbox = det["bbox"]

        # Build PLATE_DETECT task (ROI created by GPU worker)
        new_task = Task(
            category=TaskCategory.PLATE_DETECT,
            payload={       # still real plate ROI; not persisted in DB
                "car_bbox": car_bbox,
            },
            priority=0,
            video_id=video_id,
            frame_idx=frame_idx,
            track_id=task.track_id,
            meta={
                "payload_ref": payload_ref,
                "car_bbox": car_bbox,
                "dependencies": dependencies,
            },
        )

        downstream_id = db.save_task(new_task)
        queue.push(downstream_id, new_task)

        log.info(
            f"[Dispatcher] VEHICLE_DETECT → PLATE_DETECT "
            f"car_bbox={car_bbox} → task_id={downstream_id}"
        )

# ------------------------------------------------------------------------
# 2. PLATE_DETECT → OCR
# ------------------------------------------------------------------------

def handle_plate_detect_result(
    result_id: int,
    task_id: int,
    category: TaskCategory,
    task: Task,
    result_obj: List[dict],
    db: SQLiteStorage,
    queue: CentralTaskQueue,
) -> None:
    """
    result_obj = [
        { "bbox": [x1,y1,x2,y2], "conf": 0.93 },
        ...
    ]
    """

    payload_ref = task.meta.get("payload_ref")
    video_id = task.video_id
    frame_idx = task.frame_idx
    car_bbox = task.meta.get("car_bbox")
    dependencies = task.meta.get("dependencies") or ([payload_ref] if payload_ref else [])

    if not result_obj:
        log.info(f"[Dispatcher] PLATE_DETECT: no plates for task_id={task_id}")
        return

    # Choose the *best* plate detection (highest confidence)
    best = max(result_obj, key=lambda d: d["conf"])
    plate_bbox = best["bbox"]

    # Build OCR task
    new_task = Task(
        category=TaskCategory.OCR,
        payload={
            "plate_bbox": plate_bbox,
            "car_bbox": car_bbox,
        },
        priority=0,
        video_id=video_id,
        frame_idx=frame_idx,
        track_id=task.track_id,
        meta={
            "payload_ref": payload_ref,
            "car_bbox": car_bbox,
            "plate_bbox": plate_bbox,
            "dependencies": dependencies,
        },
    )

    downstream_id = db.save_task(new_task)
    queue.push(downstream_id, new_task)

    log.info(
        f"[Dispatcher] PLATE_DETECT → OCR "
        f"plate_bbox={plate_bbox} → new_task_id={downstream_id}"
    )


# ------------------------------------------------------------------------
# 3. OCR → PLATE_SMOOTH
# ------------------------------------------------------------------------

def handle_ocr_result(
    result_id: int,
    task_id: int,
    category: TaskCategory,
    task: Task,
    result_obj: dict,
    db: SQLiteStorage,
    queue: CentralTaskQueue,
) -> None:
    """
    result_obj = {
        'text': 'ABC123',
        'conf': 0.92
    }
    """

    text = result_obj.get("text", "")
    conf = result_obj.get("conf", 0.0)

    if not text:
        log.info(f"[Dispatcher] OCR: empty result for task_id={task_id}")
        return

    payload_ref = task.meta.get("payload_ref")
    video_id = task.video_id
    frame_idx = task.frame_idx
    car_bbox = task.meta.get("car_bbox")
    plate_bbox = task.meta.get("plate_bbox")
    dependencies = task.meta.get("dependencies") or ([payload_ref] if payload_ref else [])

    new_task = Task(
        category=TaskCategory.PLATE_SMOOTH,
        payload={
            "text": text,
            "conf": conf,
            "car_bbox": car_bbox,
            "plate_bbox": plate_bbox,
        },
        priority=0,
        video_id=video_id,
        frame_idx=frame_idx,
        track_id=task.track_id,
        meta={
            "payload_ref": payload_ref,
            "car_bbox": car_bbox,
            "plate_bbox": plate_bbox,
            "dependencies": dependencies,
        },
    )

    downstream_id = db.save_task(new_task)
    queue.push(downstream_id, new_task)

    log.info(
        f"[Dispatcher] OCR → PLATE_SMOOTH "
        f"text='{text}' conf={conf:.2f} → new_task_id={downstream_id}"
    )


# ------------------------------------------------------------------------
# 4. PLATE_SMOOTH → SUMMARY
# ------------------------------------------------------------------------

def handle_plate_smooth_result(
    result_id: int,
    task_id: int,
    category: TaskCategory,
    task: Task,
    result_obj: dict,
    db: SQLiteStorage,
    queue: CentralTaskQueue,
) -> None:
    """
    result_obj example:
        { "final": "ABC123" }
    """

    final_text = result_obj.get("final")
    if not final_text:
        # Not enough history yet — smoothing not done.
        return

    payload_ref = task.meta.get("payload_ref")
    video_id = task.video_id
    frame_idx = task.frame_idx
    car_bbox = task.meta.get("car_bbox")
    plate_bbox = task.meta.get("plate_bbox")
    dependencies = task.meta.get("dependencies") or ([payload_ref] if payload_ref else [])

    from pipeline.writer import get_writer
    # Write final plate data into Postgres
    writer = get_writer()
    writer.write_vehicle(
        video_id=video_id,
        frame_idx=frame_idx,
        final_plate=final_text,
        conf=result_obj.get("conf", 1.0),
        car_bbox=car_bbox,
        plate_bbox=plate_bbox,
    )

    log.info(
        f"[SUMMARY → POSTGRES] Plate='{final_text}' "
        f"video={video_id} frame={frame_idx}"
    )
