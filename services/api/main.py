from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from database import db
from media import render_clip, render_preview, resolve_video_path

app = FastAPI(
    title="Dashcam Final Data API",
    version="0.2.0",
)

OVERLAY_CHOICES = {"car_bbox", "plate_bbox", "motion"}


def _augment_links(record: dict) -> dict:
    """Attach convenience URLs for media assets."""
    if not record:
        return record
    record = dict(record)
    rid = record.get("id")
    if rid is not None:
        record["preview_url"] = f"/vehicles/{rid}/preview"
        record["clip_url"] = f"/vehicles/{rid}/clip"
    return record


def _normalize_overlays(include: list[str] | None) -> set[str]:
    overlays = set()
    for item in include or []:
        if not item:
            continue
        parts = [p.strip() for p in item.split(",") if p.strip()]
        for part in parts:
            key = part.lower()
            if key not in OVERLAY_CHOICES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid overlay '{part}'. Allowed: {sorted(OVERLAY_CHOICES)}",
                )
            overlays.add(key)
    return overlays


@app.get("/")
def root():
    return {
        "status": "ok",
        "time": str(db.test()),
    }


@app.get("/search/plates")
def search_plates(
    q: str | None = Query(None, description="Plate text to search (ILIKE + trigram)"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    video_id: str | None = Query(None, description="Optional video_id filter"),
):
    rows = db.search_vehicles(q, limit=limit, offset=offset, video_id=video_id)
    items = [_augment_links(r) for r in rows]
    return {
        "query": q,
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "items": items,
    }


@app.get("/vehicles/{vehicle_id}")
def get_vehicle(vehicle_id: int):
    record = db.get_vehicle(vehicle_id)
    if not record:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return _augment_links(record)


@app.get("/vehicles/{vehicle_id}/preview")
def vehicle_preview(vehicle_id: int):
    record = db.get_vehicle(vehicle_id)
    if not record:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    try:
        video_path = resolve_video_path(
            record.get("video_path"),
            record.get("video_filename"),
            video_id=record.get("video_id"),
        )
        image_path = render_preview(
            video_path=video_path,
            frame_idx=record["frame_idx"],
            car_bbox=record.get("car_bbox"),
            plate_bbox=record.get("plate_bbox"),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return FileResponse(
        image_path,
        media_type="image/jpeg",
        filename=image_path.name,
    )


@app.get("/vehicles/{vehicle_id}/clip")
def vehicle_clip(
    vehicle_id: int,
    window: int = Query(45, ge=5, le=240, description="Number of frames to include in the clip"),
    include: list[str] = Query(
        [],
        description="Overlay layers to render (car_bbox, plate_bbox, motion). Defaults to none.",
    ),
):
    record = db.get_vehicle(vehicle_id)
    if not record:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    overlays = _normalize_overlays(include)
    selected_frame = record.get("frame_idx")
    start_frame = max((selected_frame or 0) - window // 2, 0)
    end_frame = (selected_frame or 0) + window // 2

    motion_by_frame = None
    if overlays.intersection({"car_bbox", "motion"}) and record.get("global_id"):
        motion_by_frame = db.motion_window(
            record["global_id"],
            start_frame=start_frame,
            end_frame=end_frame,
            video_id=record.get("video_id"),
        )

    try:
        video_path = resolve_video_path(
            record.get("video_path"),
            record.get("video_filename"),
            video_id=record.get("video_id"),
        )
        clip_path, meta = render_clip(
            video_path=video_path,
            center_frame=record["frame_idx"],
            car_bbox=record.get("car_bbox"),
            plate_bbox=record.get("plate_bbox"),
            window=window,
            overlay_layers=overlays,
            motion_by_frame=motion_by_frame,
            start_frame=start_frame,
            end_frame=end_frame,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    headers = {
        "X-Clip-Start-Frame": str(meta.get("start_frame")),
        "X-Clip-End-Frame": str(meta.get("end_frame")),
        "X-Clip-Fps": str(meta.get("fps")) if meta.get("fps") else "",
        "X-Clip-Selected-Frame": str(selected_frame) if selected_frame is not None else "",
    }
    return FileResponse(
        clip_path,
        media_type="video/mp4",
        filename=clip_path.name,
        headers=headers,
    )


@app.get("/tracks/{global_id}/motion")
def track_motion(global_id: str, limit: int = Query(50, ge=1, le=500)):
    return {
        "global_id": global_id,
        "items": db.recent_motion(global_id, limit=limit),
    }


@app.get("/search/global_ids")
def search_global_ids(
    q: str | None = Query(None, description="Global ID search (ILIKE + trigram)"),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items = db.search_global_ids(q, limit=limit, offset=offset)
    return {
        "query": q,
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "items": items,
    }


def _get_record_for_global(global_id: str) -> dict:
    record = db.get_latest_vehicle_for_global(global_id)
    if not record:
        raise HTTPException(status_code=404, detail="No vehicle found for global_id")
    return record


@app.get("/global_ids/{global_id}/preview")
def global_preview(global_id: str):
    record = _get_record_for_global(global_id)
    try:
        video_path = resolve_video_path(
            record.get("video_path"),
            record.get("video_filename"),
            video_id=record.get("video_id"),
        )
        image_path = render_preview(
            video_path=video_path,
            frame_idx=record["frame_idx"],
            car_bbox=record.get("car_bbox"),
            plate_bbox=record.get("plate_bbox"),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return FileResponse(
        image_path,
        media_type="image/jpeg",
        filename=image_path.name,
    )


@app.get("/global_ids/{global_id}/clip")
def global_clip(
    global_id: str,
    frame_idx: int | None = Query(None, ge=0, description="Optional frame to center the clip; defaults to latest vehicle frame"),
    window: int = Query(45, ge=5, le=240, description="Number of frames to include in the clip"),
    include: list[str] = Query(
        [],
        description="Overlay layers to render (car_bbox, plate_bbox, motion). Defaults to none.",
    ),
):
    selected_frame = frame_idx
    overlays = _normalize_overlays(include)

    if frame_idx is not None:
        record = db.get_vehicle_for_global_frame(global_id, frame_idx)
        if not record:
            record = db.get_vehicle_for_global_nearest_frame(global_id, frame_idx)
        if record:
            selected_frame = record.get("frame_idx", frame_idx)
        else:
            raise HTTPException(status_code=404, detail="No vehicle found for that global_id/frame_idx")
    else:
        record = _get_record_for_global(global_id)
        selected_frame = record.get("frame_idx")

    start_frame = max((selected_frame or 0) - window // 2, 0)
    end_frame = (selected_frame or 0) + window // 2

    motion_by_frame = None
    if overlays.intersection({"car_bbox", "motion"}) and record.get("global_id"):
        motion_by_frame = db.motion_window(
            record["global_id"],
            start_frame=start_frame,
            end_frame=end_frame,
            video_id=record.get("video_id"),
        )

    try:
        video_path = resolve_video_path(
            record.get("video_path"),
            record.get("video_filename"),
            video_id=record.get("video_id"),
        )
        clip_path, meta = render_clip(
            video_path=video_path,
            center_frame=selected_frame if selected_frame is not None else record["frame_idx"],
            car_bbox=record.get("car_bbox"),
            plate_bbox=record.get("plate_bbox"),
            window=window,
            overlay_layers=overlays,
            motion_by_frame=motion_by_frame,
            start_frame=start_frame,
            end_frame=end_frame,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    headers = {
        "X-Clip-Start-Frame": str(meta.get("start_frame")),
        "X-Clip-End-Frame": str(meta.get("end_frame")),
        "X-Clip-Fps": str(meta.get("fps")) if meta.get("fps") else "",
        "X-Clip-Selected-Frame": str(selected_frame) if selected_frame is not None else "",
    }
    return FileResponse(
        clip_path,
        media_type="video/mp4",
        filename=clip_path.name,
        headers=headers,
    )
