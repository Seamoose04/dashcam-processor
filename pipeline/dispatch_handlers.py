# pipeline/dispatch_handlers.py
from __future__ import annotations

from typing import Any, List, Tuple
import time

from pipeline.task import Task, TaskCategory
from pipeline.queues import CentralTaskQueue
from pipeline import frame_store

from pipeline.logger import get_logger
log = get_logger("dispatch_handlers")

_PASS_THROUGH_META_KEYS = ("video_path", "video_filename", "video_ts_frame", "global_id")


def _merge_meta(task: Task, updates: dict) -> dict:
    """Carry forward shared metadata like video path while overriding stage-specific fields."""
    base = {k: task.meta[k] for k in _PASS_THROUGH_META_KEYS if k in task.meta}
    base.update(updates)
    return base


def push_with_backpressure(queue: CentralTaskQueue, task_id: int, task: Task) -> None:
    """
    Enqueue with hard-limit awareness; waits until space is available.
    """
    while not queue.push(task_id, task):
        log.warning(
            "[Enqueue] Queue %s at hard limit — pausing before retry",
            task.category.value,
        )
        time.sleep(0.01)

# ------------------------------------------------------------------------
# 1. VEHICLE_DETECT → PLATE_DETECT
# ------------------------------------------------------------------------

def handle_vehicle_detect_result(
    task: Task,
    result_obj: List[dict],
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

    spawned = 0
    for det in result_obj:
        car_bbox = det["bbox"]
        track_id = det.get("track_id") if isinstance(det, dict) else None
        global_id = f"{video_id}:{track_id}" if track_id is not None else None

        # Build PLATE_DETECT task (ROI created by GPU worker)
        new_task = Task(
            category=TaskCategory.PLATE_DETECT,
            payload={       # still real plate ROI; not persisted in DB
                "car_bbox": car_bbox,
            },
            priority=0,
            video_id=video_id,
            frame_idx=frame_idx,
            track_id=track_id if track_id is not None else task.track_id,
            meta=_merge_meta(
                task,
                {
                    "payload_ref": payload_ref,
                    "car_bbox": car_bbox,
                    "dependencies": dependencies,
                    "track_id": track_id if track_id is not None else task.track_id,
                    "global_id": global_id,
                },
            ),
        )

        downstream_id = -1  # id unused in pure in-memory mode
        frame_store.add_refs(dependencies)
        push_with_backpressure(queue, downstream_id, new_task)
        spawned += 1

        log.info(
            f"[Dispatcher] VEHICLE_DETECT → PLATE_DETECT "
            f"car_bbox={car_bbox} → task_id={downstream_id}"
        )

    # Also enqueue a VEHICLE_TRACK task for kinematics on CPU (one per frame).
    track_task = Task(
        category=TaskCategory.VEHICLE_TRACK,
        payload=result_obj,
        priority=0,
        video_id=video_id,
        frame_idx=frame_idx,
        track_id=None,
        meta=_merge_meta(
            task,
            {
                "payload_ref": payload_ref,
                "dependencies": dependencies,
                "fps": task.meta.get("fps"),
                "video_fps": task.meta.get("video_fps"),
                "video_ts_ms": task.meta.get("video_ts_ms"),
            },
        ),
    )
    frame_store.add_refs(dependencies)
    push_with_backpressure(queue, -1, track_task)
    log.info(
        "[Dispatcher] VEHICLE_DETECT → VEHICLE_TRACK video=%s frame=%s detections=%s",
        video_id,
        frame_idx,
        len(result_obj),
    )
    # Release the current task's dependency once we've spawned downstream tasks.
    # Downstream tasks hold the dependency; release occurs when they finish.

# ------------------------------------------------------------------------
# 2. PLATE_DETECT → OCR
# ------------------------------------------------------------------------

def handle_plate_detect_result(
    task: Task,
    result_obj: List[dict],
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
        log.info(
            "[Dispatcher] PLATE_DETECT: no plates for video=%s frame=%s",
            video_id,
            frame_idx,
        )
        # No downstream work; current task will be released by worker after handler returns.
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
        meta=_merge_meta(
            task,
            {
                "payload_ref": payload_ref,
                "car_bbox": car_bbox,
                "plate_bbox": plate_bbox,
                "dependencies": dependencies,
                "global_id": task.meta.get("global_id"),
            },
        ),
    )

    frame_store.add_refs(dependencies)
    push_with_backpressure(queue, -1, new_task)

    log.info(
        "[Dispatcher] PLATE_DETECT → OCR plate_bbox=%s video=%s frame=%s",
        plate_bbox,
        video_id,
        frame_idx,
    )
    # Release the current task's dependency after spawning downstream work.
    # Release happens when this task completes (worker handles it).


# ------------------------------------------------------------------------
# 2b. VEHICLE_TRACK → FINAL_WRITE (tracks + motion)
# ------------------------------------------------------------------------

def handle_vehicle_track_result(
    task: Task,
    result_obj: List[dict],
    queue: CentralTaskQueue,
) -> None:
    """
    result_obj = [
      {
        "global_id": "video:track",
        "track_id": int,
        "video_id": str,
        "frame_idx": int,
        "video_ts_frame": int,
        "video_ts_ms": float | None,
        "bbox": [...],
        "vx": float,
        "vy": float,
        "speed_px_s": float,
        "heading_deg": float,
        "age": int,
        "conf": float,
        "is_new": bool,
      },
      ...
    ]
    """
    if not result_obj:
        return

    payload_ref = task.meta.get("payload_ref")
    dependencies = task.meta.get("dependencies") or ([payload_ref] if payload_ref else [])

    for track in result_obj:
        # One-time mapping per track_id → global_id
        if track.get("is_new"):
            track_index_task = Task(
                category=TaskCategory.FINAL_WRITE,
                payload={
                    "table": "tracks",
                    "record": {
                        "global_id": track.get("global_id"),
                        "video_id": track.get("video_id") or task.video_id,
                        "track_id": track.get("track_id"),
                        "first_frame_idx": track.get("frame_idx"),
                        "video_ts_frame": track.get("video_ts_frame"),
                        "video_ts_ms": track.get("video_ts_ms"),
                        "video_path": task.meta.get("video_path"),
                        "video_filename": task.meta.get("video_filename"),
                    },
                },
                priority=0,
                video_id=task.video_id,
                frame_idx=task.frame_idx,
                track_id=track.get("track_id"),
                meta=_merge_meta(task, {"dependencies": dependencies, "payload_ref": payload_ref}),
            )
            frame_store.add_refs(dependencies)
            push_with_backpressure(queue, -1, track_index_task)

        motion_task = Task(
            category=TaskCategory.FINAL_WRITE,
            payload={
                "table": "track_motion",
                "record": {
                    "global_id": track.get("global_id"),
                    "track_id": track.get("track_id"),
                    "video_id": track.get("video_id") or task.video_id,
                    "frame_idx": track.get("frame_idx"),
                    "video_ts_frame": track.get("video_ts_frame"),
                    "video_ts_ms": track.get("video_ts_ms"),
                    "bbox": track.get("bbox"),
                    "vx": track.get("vx"),
                    "vy": track.get("vy"),
                    "speed_px_s": track.get("speed_px_s"),
                    "heading_deg": track.get("heading_deg"),
                    "age_frames": track.get("age"),
                    "conf": track.get("conf"),
                    "video_path": task.meta.get("video_path"),
                    "video_filename": task.meta.get("video_filename"),
                },
            },
            priority=0,
            video_id=task.video_id,
            frame_idx=task.frame_idx,
            track_id=track.get("track_id"),
            meta=_merge_meta(task, {"dependencies": dependencies, "payload_ref": payload_ref}),
        )
        frame_store.add_refs(dependencies)
        push_with_backpressure(queue, -1, motion_task)

    log.info(
        "[Dispatcher] VEHICLE_TRACK → FINAL_WRITE motions=%s video=%s frame=%s",
        len(result_obj),
        task.video_id,
        task.frame_idx,
    )


# ------------------------------------------------------------------------
# 3. OCR → PLATE_SMOOTH
# ------------------------------------------------------------------------

def handle_ocr_result(
    task: Task,
    result_obj: dict,
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
        log.info(
            "[Dispatcher] OCR: empty result for video=%s frame=%s",
            task.video_id,
            task.frame_idx,
        )
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
        meta=_merge_meta(
            task,
            {
                "payload_ref": payload_ref,
                "car_bbox": car_bbox,
                "plate_bbox": plate_bbox,
                "dependencies": dependencies,
                "global_id": task.meta.get("global_id"),
            },
        ),
    )

    frame_store.add_refs(dependencies)
    push_with_backpressure(queue, -1, new_task)

    log.info(
        "[Dispatcher] OCR → PLATE_SMOOTH text='%s' conf=%.2f video=%s frame=%s",
        text,
        conf,
        video_id,
        frame_idx,
    )
    # Release happens when this task completes (worker handles it).


# ------------------------------------------------------------------------
# 4. PLATE_SMOOTH → SUMMARY
# ------------------------------------------------------------------------

def handle_plate_smooth_result(
    task: Task,
    result_obj: dict,
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

    # Build FINAL_WRITE task to persist results to the external DB
    new_task = Task(
        category=TaskCategory.FINAL_WRITE,
        payload={
            "table": "vehicles",
            "record": {
                "final_plate": final_text,
                "plate_confidence": result_obj.get("conf", 1.0),
                "car_bbox": car_bbox,
                "plate_bbox": plate_bbox,
                "global_id": task.meta.get("global_id"),
            },
        },
        priority=0,
        video_id=video_id,
        frame_idx=frame_idx,
        track_id=task.track_id,
        meta=_merge_meta(
            task,
            {
                "payload_ref": payload_ref,
                "car_bbox": car_bbox,
                "plate_bbox": plate_bbox,
                "dependencies": dependencies,
                "final": final_text,
                "conf": result_obj.get("conf", 1.0),
                "global_id": task.meta.get("global_id"),
            },
        ),
    )

    frame_store.add_refs(dependencies)
    push_with_backpressure(queue, -1, new_task)

    log.info(
        "[PLATE_SMOOTH → FINAL_WRITE] Plate='%s' video=%s frame=%s",
        final_text,
        video_id,
        frame_idx,
    )
    # Release happens when this task completes (worker handles it).


# ------------------------------------------------------------------------
# 5. FINAL_WRITE (terminal)
# ------------------------------------------------------------------------

def handle_final_write_result(
    task: Task,
    result_obj: dict,
    queue: CentralTaskQueue,
) -> None:
    """
    Terminal handler: data has been persisted to the final database.
    """
    table = result_obj.get("table")
    video_id = result_obj.get("video_id") or task.video_id
    frame_idx = result_obj.get("frame_idx") or task.frame_idx

    payload_ref = task.meta.get("payload_ref")
    log.info(
        f"[FINAL_WRITE] table={table} video={video_id} frame={frame_idx} "
        f"cols={result_obj.get('columns')}"
    )
    dependencies = task.meta.get("dependencies") or []
    # Release happens when this task completes (worker handles it).
