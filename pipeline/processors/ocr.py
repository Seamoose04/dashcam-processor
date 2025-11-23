# pipeline/processors/ocr.py
from __future__ import annotations

import easyocr
import numpy as np

from pipeline import frame_store
from pipeline.task import Task
from pipeline.silence import suppress_stdout

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

    if payload_ref is None or car_bbox is None or plate_bbox is None:
        return {"text": "", "conf": 0.0}

    frame = frame_store.load_frame(payload_ref)

    cx1, cy1, cx2, cy2 = map(int, car_bbox)
    car_roi = frame[cy1:cy2, cx1:cx2]

    if car_roi.size == 0:
        return {"text": "", "conf": 0.0}

    px1, py1, px2, py2 = map(int, plate_bbox)
    plate_roi = car_roi[py1:py2, px1:px2]

    if plate_roi.size == 0:
        return {"text": "", "conf": 0.0}

    with suppress_stdout():
        results = reader.readtext(plate_roi, detail=1, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

    if not results:
        return {"text": "", "conf": 0.0}

    # pick best result
    (_, text, conf) = max(results, key=lambda r: r[2])
    return {"text": text, "conf": float(conf)}
