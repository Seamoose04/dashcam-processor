# pipeline/processors/yolo_vehicle.py
from __future__ import annotations

from ultralytics import YOLO
import numpy as np

from pipeline.task import Task

from pipeline.silence import suppress_stdout
from pipeline.logger import get_logger
log = get_logger("processor_vehicle")

# VEHICLE class IDs (COCO)
VEH_CLASSES = {2, 3, 5}   # car, motorcycle, bus/truck depending on your needs

def load_vehicle_model():
    """
    Load the YOLOv8 vehicle detection model (normally coco pretrained).
    """
    with suppress_stdout():
        return YOLO("models/yolov8n.pt")  # or your preferred detector


def process_vehicle(task: Task, model: YOLO):
    """
    VEHICLE_DETECT processor.

    Expects:
      task.payload = original frame (RGB/BGR ndarray)
      task.video_id
      task.frame_idx

    Returns:
      list of {
        'bbox': [x1, y1, x2, y2],   # frame coordinates
        'track_id': int or None,
        'conf': float
      }
    """

    frame = task.payload
    if frame is None or not isinstance(frame, np.ndarray):
        return []

    # Use YOLO 'track' OR 'predict'
    with suppress_stdout():
        results = model.track(frame, persist=True)[0]

    detections = []

    if results.boxes is not None:
        for box in results.boxes:
            cls = int(box.cls[0])
            if cls not in VEH_CLASSES:
                continue

            conf = float(box.conf[0])
            x1, y1, x2, y2 = map(float, box.xyxy[0])
            track_id = None

            # If tracker provided ID
            if hasattr(box, "id") and box.id is not None:
                try:
                    track_id = int(box.id[0])
                except Exception:
                    track_id = None

            detections.append({
                "bbox": [x1, y1, x2, y2],
                "track_id": track_id,
                "conf": conf,
            })

    return detections
