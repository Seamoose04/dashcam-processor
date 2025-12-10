import json
import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import Config
from .task_models import DetectionResult, HeavyProcessTask, OcrResult, ProcessingResult, RemoteTask

try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency
    cv2 = None
    np = None

try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - optional dependency
    YOLO = None

try:
    import easyocr
except ImportError:  # pragma: no cover - optional dependency
    easyocr = None


log = logging.getLogger(__name__)


class FrameSampler:
    def __init__(self, sample_rate: int, max_frames: int):
        self.sample_rate = max(1, sample_rate)
        self.max_frames = max_frames

    def sample(self, video_path: Path) -> List[Tuple[int, float, "np.ndarray"]]:
        if cv2 is None:
            raise RuntimeError("opencv-python is required for frame sampling")
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")
        frames: List[Tuple[int, float, "np.ndarray"]] = []
        frame_index = 0
        while len(frames) < self.max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % self.sample_rate == 0:
                timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                frames.append((frame_index, float(timestamp_ms), frame))
            frame_index += 1
        cap.release()
        log.info("Sampled %s frames from %s", len(frames), video_path)
        return frames


class PlateDetector:
    def __init__(self, model_path: Path):
        self.model_path = model_path
        self.model = None
        self.model_name = "unavailable"
        if YOLO is None:
            log.warning("ultralytics not installed; detector will return no results")
            return
        if not model_path.exists():
            log.warning("Model path %s missing; detector will return no results", model_path)
            return
        self.model = YOLO(str(model_path))
        self.model_name = model_path.name

    def detect(self, frame: "np.ndarray") -> List[Dict]:
        if self.model is None:
            return []
        results = self.model.predict(source=frame, verbose=False)
        detections: List[Dict] = []
        for res in results:
            for box in res.boxes:
                xyxy = box.xyxy[0].tolist()
                score = float(box.conf)
                cls_id = int(box.cls)
                label = self.model.names.get(cls_id, f"class_{cls_id}") if hasattr(self.model, "names") else str(cls_id)
                detections.append({"bbox": (xyxy[0], xyxy[1], xyxy[2], xyxy[3]), "score": score, "label": label})
        return detections


class OcrEngine:
    def __init__(self, enabled: bool):
        if not enabled:
            self.reader = None
            self.name = "disabled"
            return
        if easyocr is None:
            log.warning("easyocr not installed; OCR disabled")
            self.reader = None
            self.name = "missing_easyocr"
            return
        self.reader = easyocr.Reader(["en"], gpu=True)
        self.name = "easyocr"

    def read(self, crop: "np.ndarray") -> Optional[OcrResult]:
        if self.reader is None:
            return None
        results = self.reader.readtext(crop)
        if not results:
            return OcrResult(text=None, confidence=None)
        # Choose highest-confidence result
        best = max(results, key=lambda r: r[2])
        return OcrResult(text=best[1], confidence=float(best[2]))


class GpsAligner:
    def __init__(self, gps_path: Optional[str]):
        self.points: List[Dict] = []
        if not gps_path:
            return
        path = Path(gps_path)
        if not path.exists():
            log.warning("GPS path %s not found; skipping alignment", gps_path)
            return
        with path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        for entry in data:
            if "timestamp_ms" in entry and "lat" in entry and "lon" in entry:
                self.points.append(entry)
        self.points.sort(key=lambda p: p["timestamp_ms"])

    def lookup(self, timestamp_ms: Optional[float]) -> Optional[Dict[str, float]]:
        if timestamp_ms is None or not self.points:
            return None
        closest = min(self.points, key=lambda p: abs(p["timestamp_ms"] - timestamp_ms))
        return {
            "lat": closest["lat"],
            "lon": closest["lon"],
            "speed": closest.get("speed"),
            "bearing": closest.get("bearing"),
            "timestamp_ms": closest.get("timestamp_ms"),
        }


class HeavyProcessor:
    def __init__(self, config: Config):
        self.config = config
        self.detector = PlateDetector(config.models_dir / "plate.pt")
        self.ocr = OcrEngine(enabled=config.enable_ocr)
        self.frame_sampler = FrameSampler(config.frame_sample_rate, config.max_frames)

    def process(self, task: HeavyProcessTask) -> ProcessingResult:
        self.config.ensure_dirs()
        scratch_run_dir = self.config.scratch_root / f"{task.video_id}_{task.task_id}"
        output_dir = self.config.heavy_output_root / task.video_id
        self._reset_dir(scratch_run_dir, allow_existing=False)
        crops_dir = scratch_run_dir / "crops"
        crops_dir.mkdir(parents=True, exist_ok=True)

        frames = self.frame_sampler.sample(Path(task.inputs.raw_video))
        gps = GpsAligner(task.inputs.gps_path)

        detections: List[DetectionResult] = []
        for frame_idx, timestamp_ms, frame in frames:
            for det_idx, det in enumerate(self.detector.detect(frame)):
                crop = self._crop_frame(frame, det["bbox"])
                crop_path = crops_dir / f"{frame_idx}_{det_idx}.jpg"
                if cv2 is None:
                    raise RuntimeError("opencv-python is required to write crops")
                cv2.imwrite(str(crop_path), crop)
                ocr_result = self.ocr.read(crop)
                detection = DetectionResult(
                    frame_index=frame_idx,
                    bbox=det["bbox"],
                    score=det["score"],
                    class_label=det["label"],
                    timestamp_ms=timestamp_ms,
                    crop_path=str(crop_path),
                    ocr=ocr_result,
                    gps=gps.lookup(timestamp_ms),
                )
                detections.append(detection)

        metadata = {
            "task_id": task.task_id,
            "video_id": task.video_id,
            "raw_video": task.inputs.raw_video,
            "detections": [d.to_dict() for d in detections],
            "frame_count": len(frames),
            "models": {
                "detector": self.detector.model_name,
                "ocr": self.ocr.name,
            },
        }
        scratch_metadata_path = scratch_run_dir / "metadata.json"
        scratch_metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        self._reset_dir(output_dir, allow_existing=False)
        shutil.copytree(scratch_run_dir, output_dir, dirs_exist_ok=True)
        metadata_path = output_dir / "metadata.json"
        final_crops_dir = output_dir / "crops"

        if not self.config.retain_successful_runs:
            shutil.rmtree(scratch_run_dir, ignore_errors=True)

        remote_task = RemoteTask(
            task_type=self.config.archive_task_type,
            video_id=task.video_id,
            inputs={
                "video_id": task.video_id,
                "metadata_path": str(metadata_path),
                "crops_dir": str(final_crops_dir),
            },
        )
        return ProcessingResult(
            task=task,
            metadata_path=metadata_path,
            crops_dir=final_crops_dir,
            detections=detections,
            model_info={"detector": self.detector.model_name, "ocr": self.ocr.name},
            remote_tasks=[remote_task],
        )

    def _crop_frame(self, frame: "np.ndarray", bbox: Tuple[float, float, float, float]) -> "np.ndarray":
        if cv2 is None or np is None:
            raise RuntimeError("opencv-python and numpy are required for cropping")
        x1, y1, x2, y2 = bbox
        h, w = frame.shape[:2]
        x1_i = max(0, int(x1))
        y1_i = max(0, int(y1))
        x2_i = min(w, int(x2))
        y2_i = min(h, int(y2))
        return frame[y1_i:y2_i, x1_i:x2_i]

    def _reset_dir(self, path: Path, allow_existing: bool) -> None:
        path = path.expanduser()
        roots = [self.config.scratch_root.resolve(), self.config.heavy_output_root.resolve()]
        if not any(self._is_relative_to(path, root) for root in roots):
            raise RuntimeError(f"Refusing to modify directory outside managed roots: {path}")
        if path.exists() and not allow_existing:
            shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _is_relative_to(path: Path, other: Path) -> bool:
        try:
            path.resolve().relative_to(other)
            return True
        except ValueError:
            return False
