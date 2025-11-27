import os
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from pipeline.writer import get_writer

# Keys that control writing rather than belonging to the record itself.
_CONTROL_KEYS = {"table", "record", "extra", "metadata"}


def load_final_writer():
    """Load a shared Writer instance for CPU workers."""
    return get_writer()


def _build_record(task, payload: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Normalize payload into (table, record) tuple for the writer.
    Allows flexible payload shapes so upstream stages can attach arbitrary data.
    """
    if not isinstance(payload, dict):
        raise ValueError(f"FINAL_WRITE payload must be a dict, got {type(payload)}")

    table = payload.get("table") or "vehicles"

    base_record = payload.get("record")
    if base_record is None:
        # Treat payload (minus control keys) as the record if no explicit record is provided.
        base_record = {k: v for k, v in payload.items() if k not in _CONTROL_KEYS}
    elif not isinstance(base_record, dict):
        raise ValueError("FINAL_WRITE payload.record must be a dict")

    record: Dict[str, Any] = dict(base_record)

    # Merge any extra/metadata dict without overwriting explicit record keys.
    extra_meta = payload.get("extra") or payload.get("metadata")
    if isinstance(extra_meta, dict):
        for k, v in extra_meta.items():
            record.setdefault(k, v)

    # Backfill common IDs from the task if not explicitly provided.
    if task.video_id is not None:
        record.setdefault("video_id", task.video_id)
    if task.frame_idx is not None:
        record.setdefault("frame_idx", task.frame_idx)
    if task.track_id is not None:
        record.setdefault("track_id", task.track_id)
    if "video_ts_frame" not in record:
        if "video_ts_frame" in task.meta:
            record["video_ts_frame"] = task.meta["video_ts_frame"]
        elif task.frame_idx is not None:
            record["video_ts_frame"] = task.frame_idx

    # Bring forward often-needed metadata if present.
    for field in ("car_bbox", "plate_bbox"):
        if field not in record and field in task.meta:
            record[field] = task.meta[field]

    if "final_plate" not in record and "final" in task.meta:
        record["final_plate"] = task.meta["final"]

    if "plate_confidence" not in record:
        meta_conf = task.meta.get("conf")
        if meta_conf is not None:
            record["plate_confidence"] = meta_conf
        elif "conf" in payload:
            record["plate_confidence"] = payload["conf"]
    if "video_path" not in record and "video_path" in task.meta:
        record["video_path"] = task.meta["video_path"]
    if "video_filename" not in record:
        if "video_filename" in task.meta:
            record["video_filename"] = task.meta["video_filename"]
        elif "video_path" in record:
            record["video_filename"] = os.path.basename(record["video_path"])
        elif "video_path" in task.meta:
            record["video_filename"] = os.path.basename(task.meta["video_path"])

    # Vehicles table defaults/validation
    if table == "vehicles":
        record.setdefault("ts", datetime.now(timezone.utc))

        required = [
            "video_id",
            "frame_idx",
            "ts",
            "final_plate",
            "plate_confidence",
            "car_bbox",
            "plate_bbox",
        ]
        missing = [k for k in required if k not in record or record[k] is None]
        if missing:
            raise ValueError(f"FINAL_WRITE missing required fields for vehicles: {missing}")

    return table, record


def process_final_writer(task, writer):
    """
    Write finalized records to the external database.

    Expected payload shapes (flexible):
    - {"table": "vehicles", "record": {...}}
    - {"table": "vehicles", "final_plate": "...", "plate_confidence": 0.9, ...}
    - {"record": {...}}  # defaults to vehicles table
    """
    payload = task.payload or {}
    table, record = _build_record(task, payload)
    writer.write_record(table, record)

    return {
        "table": table,
        "columns": list(record.keys()),
        "video_id": record.get("video_id"),
        "frame_idx": record.get("frame_idx"),
    }
