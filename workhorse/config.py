from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    server_url: str
    api_key: Optional[str]
    scratch_root: Path
    nas_mount: Path
    heavy_output_root: Path
    models_dir: Path
    poll_interval_seconds: float
    frame_sample_rate: int
    max_frames: int
    retain_successful_runs: bool
    enable_ocr: bool
    task_type: str = "HEAVY_PROCESS_VIDEO"
    archive_task_type: str = "ARCHIVE_VIDEO"

    @classmethod
    def from_env(cls) -> "Config":
        server_url = os.getenv("DASHCAM_SERVER_URL", "http://localhost:8000").rstrip("/")
        api_key = os.getenv("DASHCAM_API_KEY") or None
        scratch_root = Path(os.getenv("DASHCAM_SCRATCH_ROOT", "workstation/.scratch")).expanduser()
        nas_mount = Path(os.getenv("DASHCAM_NAS_MOUNT", "/mnt/indoor_nas")).expanduser()
        models_dir = Path(os.getenv("DASHCAM_MODELS_DIR", "models")).expanduser()
        heavy_output_root_env = os.getenv("DASHCAM_HEAVY_OUTPUT_ROOT")
        heavy_output_root = (
            Path(heavy_output_root_env).expanduser()
            if heavy_output_root_env
            else nas_mount / "videos" / "heavy_output"
        )
        poll_interval_seconds = float(os.getenv("DASHCAM_POLL_INTERVAL", "10"))
        frame_sample_rate = int(os.getenv("DASHCAM_FRAME_SAMPLE_RATE", "10"))
        max_frames = int(os.getenv("DASHCAM_MAX_FRAMES", "300"))
        retain_successful_runs = os.getenv("DASHCAM_RETAIN_RUNS", "false").lower() in ("1", "true", "yes")
        enable_ocr = os.getenv("DASHCAM_ENABLE_OCR", "true").lower() in ("1", "true", "yes")
        return cls(
            server_url=server_url,
            api_key=api_key,
            scratch_root=scratch_root,
            nas_mount=nas_mount,
            heavy_output_root=heavy_output_root,
            models_dir=models_dir,
            poll_interval_seconds=poll_interval_seconds,
            frame_sample_rate=frame_sample_rate,
            max_frames=max_frames,
            retain_successful_runs=retain_successful_runs,
            enable_ocr=enable_ocr,
        )

    def ensure_dirs(self) -> None:
        self.scratch_root.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.heavy_output_root.mkdir(parents=True, exist_ok=True)
