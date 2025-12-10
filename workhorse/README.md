# 4090 Workstation Worker

This folder contains the worker that runs on the RTX 4090 workstation. It pulls `HEAVY_PROCESS_VIDEO` tasks from the main server, performs GPU-heavy processing (YOLO detection + OCR + GPS alignment), writes heavy outputs to the Indoor NAS, and publishes the downstream archival task.

## Quick start

1. Install Python 3.10+ with CUDA-enabled drivers.
2. Install dependencies (example):
   ```bash
   pip install -r requirements.txt
   ```
3. Set environment variables (see below).
4. Run the worker:
   ```bash
   python -m workstation.worker
   ```
   Use `--once` to process a single task for debugging.

## Configuration (env vars)

- `DASHCAM_SERVER_URL` — base URL of the main server API (default `http://localhost:8000`).
- `DASHCAM_API_KEY` — optional bearer token for the API.
- `DASHCAM_SCRATCH_ROOT` — local SSD scratch space for in-progress work (default `workstation/.scratch`).
- `DASHCAM_NAS_MOUNT` — Indoor NAS mount root (default `/mnt/indoor_nas`).
- `DASHCAM_HEAVY_OUTPUT_ROOT` — where finalized heavy outputs are stored; defaults to `<NAS>/videos/heavy_output`.
- `DASHCAM_MODELS_DIR` — directory containing YOLO weights (default `models/`).
- `DASHCAM_POLL_INTERVAL` — seconds between polls when idle (default `10`).
- `DASHCAM_FRAME_SAMPLE_RATE` — sample every Nth frame when running YOLO (default `10`).
- `DASHCAM_MAX_FRAMES` — cap on sampled frames per video (default `300`).
- `DASHCAM_ENABLE_OCR` — set to `false` to skip OCR.
- `DASHCAM_RETAIN_RUNS` — set to `true` to keep scratch artifacts after success.

## What the worker does

1. Polls the server for the oldest `HEAVY_PROCESS_VIDEO` task via `GET /tasks/next?task_type=...`.
2. Samples frames from the raw video on the NAS.
3. Runs YOLO plate detection (using `models/plate.pt`), extracts crops, and runs OCR if enabled.
4. Writes metadata and crops to `<DASHCAM_HEAVY_OUTPUT_ROOT>/<video_id>/`.
5. Publishes a remote `ARCHIVE_VIDEO` task in the completion payload so the server can move outputs to the Shed NAS and update metadata.
6. Cleans scratch space on startup (local tasks are always ephemeral).

## Notes

- Dependencies such as `ultralytics`, `opencv-python`, and `easyocr` are optional at import time but required for real processing. If they are missing, the worker logs warnings and returns empty detections.
- Heavy outputs are written to the NAS so the main server or Shed NAS can pick them up during archival.
- Temporary scratch data lives under `DASHCAM_SCRATCH_ROOT` and is wiped on startup unless `--skip-scratch-clean` is passed.
