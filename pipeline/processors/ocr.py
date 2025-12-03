# pipeline/processors/ocr.py
from __future__ import annotations

import os
import easyocr
import numpy as np

from pipeline import frame_store
from pipeline.task import Task
from pipeline.silence import suppress_stdout
from pipeline.logger import get_logger

# Optional debug logging: set OCR_DEBUG_RESULTS=1 to log raw EasyOCR tuples.
_DEBUG = os.environ.get("OCR_DEBUG_RESULTS", "0") != "0"
_DEBUG_MAX = int(os.environ.get("OCR_DEBUG_MAX", "5"))
_log = get_logger("ocr_debug")


def _merge_plate_text(results):
    """
    EasyOCR sometimes splits plates (e.g. around a center graphic) into multiple
    bounding boxes. Merge horizontally ordered detections that live on the same
    line so we keep the full plate instead of only the highest-confidence half.
    """
    detections = []
    for r in results:
        if len(r) >= 3:
            bbox, text, conf = r[0], r[1], r[2]
        elif len(r) == 2:
            bbox, text = r
            conf = None
        else:
            continue  # unexpected shape, skip
        if not text or bbox is None:
            continue
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        detections.append(
            {
                "x1": min(xs),
                "x2": max(xs),
                "y1": min(ys),
                "y2": max(ys),
                "text": text.strip(),
                "conf": float(conf),
            }
        )

    if not detections:
        return "", 0.0

    # Sort left-to-right; plates are single-line so group everything on the
    # dominant row (vertical overlap with the first detection).
    detections.sort(key=lambda d: d["x1"])
    line_center = 0.5 * (detections[0]["y1"] + detections[0]["y2"])
    line_height = detections[0]["y2"] - detections[0]["y1"]
    merged = []
    for d in detections:
        center = 0.5 * (d["y1"] + d["y2"])
        height = d["y2"] - d["y1"]
        if abs(center - line_center) <= max(line_height, height):
            merged.append(d)

    if not merged:
        merged = [detections[0]]

    text = "".join(d["text"] for d in merged)
    confs = [d["conf"] for d in merged if d.get("conf") is not None]
    conf = float(np.mean(confs)) if confs else 0.0
    return text, conf


def _format_result_entry(entry):
    """Make raw EasyOCR entries log-friendly without dumping huge arrays."""
    if len(entry) == 3:
        bbox, text, conf = entry
    elif len(entry) == 2:
        bbox, text = entry
        conf = None
    else:
        return {"len": len(entry), "entry": str(entry)}

    return {
        "bbox_shape": np.shape(bbox),
        "text": text,
        "conf": conf,
    }


def load_ocr():
    # OCR on CPU
    with suppress_stdout():
        return easyocr.Reader(["en"], gpu=True)


def process_ocr(task: Task, reader: easyocr.Reader):
    """
    OCR processor.

    Expects:
      task.meta['payload_ref'] = 'video_id:frame_idx'
      task.meta['car_bbox']    = [cx1, cy1, cx2, cy2] frame coords
      task.meta['plate_bbox']  = [px1, py1, px2, py2] coords *within car ROI*
    """
    payload_ref = task.meta.get("payload_ref")
    car_bbox = task.meta.get("car_bbox")
    plate_bbox = task.meta.get("plate_bbox")
    payload_plate = task.payload.get("plate_roi") if isinstance(task.payload, dict) else None

    if payload_plate is not None:
        plate_roi = payload_plate
    else:
        if payload_ref is None or car_bbox is None or plate_bbox is None:
            return {"text": "", "conf": 0.0}

        frame = frame_store.load_frame(payload_ref)

        cx1, cy1, cx2, cy2 = map(int, car_bbox)
        car_roi = frame[cy1:cy2, cx1:cx2]

        if car_roi.size == 0:
            return {"text": "", "conf": 0.0}

        px1, py1, px2, py2 = map(int, plate_bbox)
        plate_roi = car_roi[py1:py2, px1:px2]

    if plate_roi is None or plate_roi.size == 0:
        return {"text": "", "conf": 0.0}

    with suppress_stdout():
        results = reader.readtext(
            plate_roi,
            detail=1,
            allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            paragraph=False,  # get per-box confidences; we merge manually
            width_ths=0.2,    # be less aggressive about splitting close characters
        )

    if _DEBUG:
        formatted = [_format_result_entry(r) for r in results[:_DEBUG_MAX]]
        _log.info(
            "[OCR_DEBUG] video=%s frame=%s track=%s results=%s (total=%s)",
            task.video_id,
            task.frame_idx,
            task.track_id,
            formatted,
            len(results),
        )

    if not results:
        return {"text": "", "conf": 0.0}

    merged_text, merged_conf = _merge_plate_text(results)
    if merged_text:
        return {"text": merged_text, "conf": merged_conf}

    # fallback: pick best individual detection
    best = max(results, key=lambda r: r[2] if len(r) > 2 and r[2] is not None else 0.0)
    text = best[1] if len(best) > 1 else ""
    conf = best[2] if len(best) > 2 and best[2] is not None else 0.0
    return {"text": text, "conf": float(conf)}
