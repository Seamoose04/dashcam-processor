# pipeline/processors/yolo_plate.py
from __future__ import annotations

from ultralytics import YOLO
import numpy as np

from pipeline import frame_store
from pipeline.task import Task

from pipeline.silence import suppress_stdout
from pipeline.logger import get_logger
log = get_logger("processor_vehicle")

def load_plate_model():
    # Your retrained plate detector
    with suppress_stdout():
        return YOLO("models/plate.pt")

def process_plate(task: Task, model: YOLO):
    """
    PLATE_DETECT processor.

    Expects:
      task.meta['payload_ref'] = 'video_id:frame_idx'
      task.meta['car_bbox']    = [x1, y1, x2, y2]  (frame coordinates)

    Returns:
      list of {
        'bbox': [x1, y1, x2, y2],  # ROI-local coords (within car ROI)
        'conf': float
      }
    """
    payload_ref = task.meta.get("payload_ref")
    car_bbox = task.meta.get("car_bbox")
    if payload_ref is None or car_bbox is None:
        return []

    # Load original frame from FrameStore
    frame = frame_store.load_frame(payload_ref)
    x1, y1, x2, y2 = map(int, car_bbox)
    car_roi = frame[y1:y2, x1:x2]

    if car_roi.size == 0:
        return []

    with suppress_stdout():
        results = model(car_roi)[0]

    plates = []
    if results.boxes is not None:
        for box in results.boxes:
            px1, py1, px2, py2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            plates.append({
                "bbox": [px1, py1, px2, py2],  # ROI-local coords
                "conf": conf,
            })

    return plates
