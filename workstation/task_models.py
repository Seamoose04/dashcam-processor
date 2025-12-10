from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


BBox = Tuple[float, float, float, float]


@dataclass
class TaskInputPaths:
    raw_video: str
    preproc_json: Optional[str] = None
    gps_path: Optional[str] = None
    thumbnails_dir: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "TaskInputPaths":
        return cls(
            raw_video=data["raw_video"],
            preproc_json=data.get("preproc_json"),
            gps_path=data.get("gps_path"),
            thumbnails_dir=data.get("thumbnails_dir"),
        )


@dataclass
class HeavyProcessTask:
    task_id: str
    video_id: str
    inputs: TaskInputPaths
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> "HeavyProcessTask":
        return cls(
            task_id=str(data["task_id"]),
            video_id=data["video_id"],
            inputs=TaskInputPaths.from_dict(data["inputs"]),
            created_at=data.get("created_at"),
        )


@dataclass
class OcrResult:
    text: Optional[str]
    confidence: Optional[float]

    def to_dict(self) -> Dict:
        return {"text": self.text, "confidence": self.confidence}


@dataclass
class DetectionResult:
    frame_index: int
    bbox: BBox
    score: float
    class_label: str
    timestamp_ms: Optional[float]
    crop_path: Optional[str] = None
    ocr: Optional[OcrResult] = None
    gps: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict:
        return {
            "frame_index": self.frame_index,
            "bbox": list(self.bbox),
            "score": self.score,
            "class_label": self.class_label,
            "timestamp_ms": self.timestamp_ms,
            "crop_path": self.crop_path,
            "ocr": self.ocr.to_dict() if self.ocr else None,
            "gps": self.gps,
        }


@dataclass
class RemoteTask:
    task_type: str
    video_id: str
    inputs: Dict

    def to_dict(self) -> Dict:
        return {"task_type": self.task_type, "video_id": self.video_id, "inputs": self.inputs}


@dataclass
class ProcessingResult:
    task: HeavyProcessTask
    metadata_path: Path
    crops_dir: Optional[Path]
    detections: List[DetectionResult] = field(default_factory=list)
    model_info: Dict = field(default_factory=dict)
    remote_tasks: List[RemoteTask] = field(default_factory=list)

    def to_payload(self) -> Dict:
        return {
            "video_id": self.task.video_id,
            "task_id": self.task.task_id,
            "metadata_path": str(self.metadata_path),
            "crops_dir": str(self.crops_dir) if self.crops_dir else None,
            "detections": [d.to_dict() for d in self.detections],
            "model_info": self.model_info,
            "remote_tasks": [t.to_dict() for t in self.remote_tasks],
        }
