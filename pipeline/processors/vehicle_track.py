from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from pipeline.task import Task


def load_vehicle_tracker() -> Dict[str, Any]:
    """
    Create a per-process tracker state. We key tracks by (video_id, detector track_id).
    """
    return {
        "videos": {},  # video_id -> {"tracks": {track_id: state}, "next_id": int}
    }

# Max speed clamp (pixels per second) to prevent wild spikes on detector jumps.
MAX_SPEED_PX_S = 3000.0
# Simple exponential smoothing for velocity to reduce jitter.
SPEED_SMOOTH_ALPHA = 0.5


def _center(bbox: List[float]) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) * 0.5, (y1 + y2) * 0.5


def _speed_heading(prev_center, curr_center, dt_s: float) -> Tuple[float, float, float, float]:
    """
    Returns (vx, vy, speed, heading_deg).
    Heading uses image coords (x right, y down).
    """
    if dt_s <= 1e-6:
        dt_s = 1e-3
    px, py = prev_center
    cx, cy = curr_center
    vx = (cx - px) / dt_s
    vy = (cy - py) / dt_s
    speed = math.hypot(vx, vy)
    heading_deg = math.degrees(math.atan2(vy, vx)) if speed > 0 else 0.0
    return vx, vy, speed, heading_deg


def _default_video_state():
    return {"tracks": {}, "next_id": 1}


def process_vehicle_track(task: Task, state: Dict[str, Any]) -> List[dict]:
    """
    Consume detector outputs (with track_ids) and compute velocity/heading on CPU.

    Input (task.payload):
      [
        {"bbox": [x1,y1,x2,y2], "track_id": int, "conf": float},
        ...
      ]
    Uses task.meta['fps'] or defaults to 30fps when timestamps are missing.
    """
    detections = task.payload or []
    if not isinstance(detections, list):
        return []

    video_id = task.video_id or "unknown"
    frame_idx = task.frame_idx or -1
    fps = task.meta.get("fps") or task.meta.get("video_fps") or 30.0
    ts_ms = task.meta.get("video_ts_ms")

    videos = state["videos"]
    video_state = videos.setdefault(video_id, _default_video_state())
    tracks = video_state["tracks"]

    results = []

    for det in detections:
        track_id = det.get("track_id")
        if track_id is not None:
            try:
                track_id = int(track_id)
            except Exception:
                continue
        bbox = det.get("bbox")
        if track_id is None or bbox is None:
            continue

        conf = float(det.get("conf", 0.0))
        x1, y1, x2, y2 = bbox
        width = float(abs(x2 - x1))
        height = float(abs(y2 - y1))
        area = width * height
        global_id = f"{video_id}:{track_id}"

        prev = tracks.get(track_id)
        is_new = prev is None
        dt_s = None

        if ts_ms is not None and prev and prev.get("ts_ms") is not None:
            dt_s = max(1e-3, (ts_ms - prev["ts_ms"]) / 1000.0)
        elif prev and fps > 0:
            frame_delta = max(1, frame_idx - prev.get("frame_idx", frame_idx - 1))
            dt_s = frame_delta / fps
        else:
            dt_s = 1.0 / fps if fps > 0 else 0.033

        if prev:
            prev_center = prev["center"]
        else:
            prev_center = _center(bbox)

        curr_center = _center(bbox)
        vx, vy, speed, heading_deg = _speed_heading(prev_center, curr_center, dt_s)

        # Clamp extreme speeds and scale velocity accordingly
        if speed > MAX_SPEED_PX_S:
            scale = MAX_SPEED_PX_S / speed
            vx *= scale
            vy *= scale
            speed = MAX_SPEED_PX_S
            heading_deg = math.degrees(math.atan2(vy, vx)) if speed > 0 else 0.0

        # Smooth velocity to reduce jitter/frame gaps
        if prev and "svx" in prev and "svy" in prev:
            pvx, pvy = prev["svx"], prev["svy"]
            vx = SPEED_SMOOTH_ALPHA * vx + (1 - SPEED_SMOOTH_ALPHA) * pvx
            vy = SPEED_SMOOTH_ALPHA * vy + (1 - SPEED_SMOOTH_ALPHA) * pvy
            speed = math.hypot(vx, vy)
            heading_deg = math.degrees(math.atan2(vy, vx)) if speed > 0 else 0.0

        # Scale dynamics from bbox size
        prev_area = prev.get("area") if prev else None
        scale_ratio = (area / prev_area) if prev_area and prev_area > 0 else 1.0
        scale_rate = 0.0
        if prev_area is not None and dt_s is not None and dt_s > 0:
            scale_rate = (area - prev_area) / dt_s

        tracks[track_id] = {
            "bbox": bbox,
            "center": curr_center,
            "frame_idx": frame_idx,
            "ts_ms": ts_ms,
            "vx": vx,
            "vy": vy,
            "svx": vx,  # smoothed velocity
            "svy": vy,
            "speed": speed,
            "heading_deg": heading_deg,
            "age": (prev.get("age", 0) + 1) if prev else 1,
            "conf": conf,
            "global_id": global_id,
            "area": area,
        }

        results.append(
            {
                "global_id": global_id,
                "track_id": track_id,
                "video_id": video_id,
                "frame_idx": frame_idx,
                "video_ts_frame": task.meta.get("video_ts_frame", frame_idx),
                "video_ts_ms": ts_ms,
                "bbox": bbox,
                "bbox_w": width,
                "bbox_h": height,
                "bbox_area": area,
                "scale_rate": scale_rate,    # area units per second
                "scale_ratio": scale_ratio,  # relative to previous frame
                "vx": vx,
                "vy": vy,
                "speed_px_s": speed,
                "heading_deg": heading_deg,
                "age": tracks[track_id]["age"],
                "conf": conf,
                "is_new": is_new,
            }
        )

    # Optionally prune stale tracks: any track not seen on this frame gets a miss count.
    if tracks:
        track_ids_seen = {r["track_id"] for r in results}
        for tid in list(tracks.keys()):
            if tid not in track_ids_seen:
                tracks[tid]["age"] = tracks[tid].get("age", 0)

    return results
