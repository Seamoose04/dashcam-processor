import os
from pathlib import Path
import glob
from typing import Any, Dict, Optional, Tuple

import cv2

# Where generated previews/snippets are stored and served from.
SNIPPET_ROOT = Path(os.getenv("SNIPPET_ROOT", "frame_store/snippets")).resolve()
SNIPPET_ROOT.mkdir(parents=True, exist_ok=True)


def resolve_video_path(video_path: Optional[str], video_filename: Optional[str], *, video_id: Optional[str] = None) -> Path:
    """
    Resolve the on-disk path to a source video.
    Prefers the stored absolute/relative path, falling back to VIDEO_ROOT + filename.
    """
    candidates = []

    if video_path:
        candidates.append(Path(video_path))

    if video_filename:
        candidates.append(Path(video_filename))
        video_root = Path(os.getenv("VIDEO_ROOT", "/app/videos"))
        candidates.append(video_root / video_filename)

    for path in candidates:
        if path and path.is_file():
            return path.resolve()

    # Fallback: try to find a file matching the video_id.* pattern under VIDEO_ROOT
    if video_id:
        video_root = Path(os.getenv("VIDEO_ROOT", "inputs"))
        matches = glob.glob(str(video_root / f"{video_id}.*"))
        for m in matches:
            candidate = Path(m)
            if candidate.is_file():
                return candidate.resolve()

    raise FileNotFoundError(f"Unable to locate video for record (video_path={video_path}, filename={video_filename})")


def _coerce_bbox(bbox: Any) -> Optional[Tuple[int, int, int, int]]:
    """
    Convert bbox JSON (list/tuple/dict) to integer tuple.
    """
    if bbox is None:
        return None
    if isinstance(bbox, dict):
        # Accept either standard keys or numeric indices.
        keys = ["x1", "y1", "x2", "y2"]
        if all(k in bbox for k in keys):
            vals = [bbox[k] for k in keys]
        else:
            vals = list(bbox.values())
    else:
        vals = list(bbox)

    if len(vals) < 4:
        return None

    nums = [int(round(float(v))) for v in vals[:4]]
    return tuple(nums)  # type: ignore[return-value]


def _draw_boxes(
    frame,
    car_bbox: Optional[Tuple[int, int, int, int]],
    plate_bbox: Optional[Tuple[int, int, int, int]],
):
    """
    Overlay car + plate bounding boxes on a frame.
    """
    if car_bbox:
        x1, y1, x2, y2 = car_bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
    if plate_bbox:
        x1, y1, x2, y2 = plate_bbox
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
    return frame


def _draw_motion_vector(
    frame,
    motion: Optional[Dict[str, Any]],
    bbox: Optional[Tuple[int, int, int, int]],
    fps: float,
):
    """
    Overlay a motion vector arrow for the frame. Uses bbox center when available.
    """
    if not motion:
        return frame
    vx = motion.get("vx")
    vy = motion.get("vy")
    if vx is None or vy is None:
        return frame

    h, w = frame.shape[:2]
    if bbox:
        x1, y1, x2, y2 = bbox
        start = (int(round((x1 + x2) * 0.5)), int(round((y1 + y2) * 0.5)))
    else:
        start = (w // 2, h // 2)

    # Convert px/s to px/frame for visualization; clamp to avoid zero-length arrows.
    step = max(fps, 1e-3)
    dx = int(round(float(vx) / step))
    dy = int(round(float(vy) / step))
    if dx == 0 and dy == 0:
        if abs(float(vx)) >= abs(float(vy)):
            dx = 1 if float(vx) >= 0 else -1
        else:
            dy = 1 if float(vy) >= 0 else -1
    end = (start[0] + dx, start[1] + dy)

    cv2.arrowedLine(frame, start, end, (255, 0, 0), 2, tipLength=0.25)
    return frame


def _read_frame_at(video_path: Path, frame_idx: int):
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError(f"Could not read frame {frame_idx} from {video_path}")
    return frame


def render_preview(
    *,
    video_path: Path,
    frame_idx: int,
    car_bbox: Any = None,
    plate_bbox: Any = None,
) -> Path:
    """
    Generate (or return cached) JPEG preview for a detection with bounding boxes.
    """
    stem = video_path.stem
    out_path = SNIPPET_ROOT / f"{stem}_{frame_idx}_preview.jpg"
    if out_path.exists():
        return out_path

    frame = _read_frame_at(video_path, frame_idx)
    boxed = _draw_boxes(frame, _coerce_bbox(car_bbox), _coerce_bbox(plate_bbox))
    ok = cv2.imwrite(str(out_path), boxed)
    if not ok:
        raise RuntimeError(f"Failed to write preview to {out_path}")
    return out_path


def render_clip(
    *,
    video_path: Path,
    center_frame: int,
    car_bbox: Any = None,
    plate_bbox: Any = None,
    window: int = 45,
    overlay_layers: Optional[set[str]] = None,
    motion_by_frame: Optional[Dict[int, Dict[str, Any]]] = None,
    start_frame: Optional[int] = None,
    end_frame: Optional[int] = None,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Render a short MP4 clip around the target frame with optional overlays.
    """
    stem = video_path.stem
    overlays = overlay_layers or set()
    overlay_tag = "-".join(sorted(overlays)) if overlays else "none"
    out_path = SNIPPET_ROOT / f"{stem}_{center_frame}_w{window}_ovl-{overlay_tag}.mp4"

    # Boundaries for motion lookup and clip positioning.
    clip_start = start_frame if start_frame is not None else max(center_frame - window // 2, 0)
    clip_end = end_frame if end_frame is not None else center_frame + window // 2
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path, {
            "start_frame": clip_start,
            "end_frame": clip_end,
        }

    cap = cv2.VideoCapture(str(video_path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    cap.set(cv2.CAP_PROP_POS_FRAMES, clip_start)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))

    use_car = "car_bbox" in overlays
    use_plate = "plate_bbox" in overlays
    use_motion = "motion" in overlays

    car_static = _coerce_bbox(car_bbox) if use_car else None
    plate_static = _coerce_bbox(plate_bbox) if use_plate else None

    written = 0
    frame_idx = clip_start
    while frame_idx <= clip_end:
        ok, frame = cap.read()
        if not ok or frame is None:
            break

        motion = motion_by_frame.get(frame_idx) if motion_by_frame else None
        car_box = car_static
        plate_box = plate_static

        if use_car and motion and motion.get("bbox") is not None:
            car_box = _coerce_bbox(motion.get("bbox")) or car_static
        if use_plate and motion and motion.get("plate_bbox") is not None:
            plate_box = _coerce_bbox(motion.get("plate_bbox"))

        if use_car or use_plate:
            frame = _draw_boxes(frame, car_box if use_car else None, plate_box if use_plate else None)
        if use_motion:
            frame = _draw_motion_vector(frame, motion, car_box, fps)

        writer.write(frame)
        written += 1
        frame_idx += 1

    writer.release()
    cap.release()

    if written == 0 or not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"Failed to render clip to {out_path}")

    meta = {
        "start_frame": clip_start,
        "end_frame": clip_start + written - 1,
        "fps": fps,
    }
    return out_path, meta
