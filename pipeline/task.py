# pipeline/task.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional, Dict


class ResourceType(Enum):
    CPU = auto()
    GPU = auto()


class TaskCategory(Enum):
    """
    High-level task types for the pipeline.

    You can add more as the project grows:
    - EMBEDDING
    - CLUSTERING
    - SUMMARY
    etc.
    """
    VEHICLE_DETECT = "vehicle_yolo"   # YOLOv8 on full frame
    PLATE_DETECT = "plate_yolo"       # YOLOv8 on car ROI
    OCR = "ocr"                       # EasyOCR on plate crops
    PLATE_SMOOTH = "plate_smooth"     # temporal merge of OCR
    SUMMARY = "summary"               # vehicle/plate-level summary
    FINAL_WRITE = "final_write"       # writes finalized data to the external DB


@dataclass
class Task:
    """
    Generic unit of work in the pipeline.

    `payload` is intentionally untyped so it can be:
    - raw frame (np.ndarray)
    - cropped ROI
    - metadata dict
    - anything else downstream needs
    """
    category: TaskCategory
    payload: Any

    # Optional metadata for traceability
    priority: int = 0                 # higher = sooner
    video_id: Optional[str] = None
    frame_idx: Optional[int] = None
    track_id: Optional[int] = None

    # Arbitrary extra metadata
    meta: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        base = f"Task(category={self.category.value}, priority={self.priority}"
        if self.video_id is not None:
            base += f", video_id={self.video_id}"
        if self.frame_idx is not None:
            base += f", frame_idx={self.frame_idx}"
        if self.track_id is not None:
            base += f", track_id={self.track_id}"
        return base + ")"
