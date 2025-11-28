from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from database import db
from media import render_clip, render_preview, resolve_video_path

app = FastAPI(
    title="Dashcam Final Data API",
    version="0.2.0",
)


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
):
    record = db.get_vehicle(vehicle_id)
    if not record:
        raise HTTPException(status_code=404, detail="Vehicle not found")

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
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    headers = {
        "X-Clip-Start-Frame": str(meta.get("start_frame")),
        "X-Clip-End-Frame": str(meta.get("end_frame")),
        "X-Clip-Fps": str(meta.get("fps")) if meta.get("fps") else "",
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
