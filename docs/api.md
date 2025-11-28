# Dashcam API

FastAPI service that exposes processed pipeline results (plates, tracks) and serves previews/clips with bounding boxes.

## Running the API
- With Docker Compose (recommended):
  - `export POSTGRES_PASSWORD=yourpass`
  - `docker compose up --build -d finaldb dashcam_api`
  - Initialize schema (first run): `docker compose exec dashcam_api python setup_db.py`
  - API base: `http://localhost:8001`
- Without Docker:
  - `pip install -r services/api/requirements.txt`
  - Set `POSTGRES_*` env vars to your DB (host/user/pass/db/port).
  - Optional media lookup overrides: `VIDEO_ROOT` (defaults to `inputs`), `SNIPPET_ROOT` (defaults to `frame_store/snippets`).
  - Run: `uvicorn services.api.main:app --reload --port 8001`

## Endpoints
- `GET /` — health check; returns DB time.
- `GET /search/plates?q=ABC&limit=25&offset=0&video_id=...`
  - Searches `vehicles.final_plate` via `ILIKE` + trigram similarity.
  - Each item includes `preview_url` and `clip_url`.
- `GET /vehicles/{id}`
  - Fetch a single vehicle row (plate, bboxes, video/frame metadata).
- `GET /vehicles/{id}/preview`
  - JPEG frame with car/plate boxes overlaid. Caches under `SNIPPET_ROOT`.
- `GET /vehicles/{id}/clip?window=45`
  - MP4 clip centered on the detection frame with boxes. `window` is frame count (default 45).
  - Response headers include `X-Clip-Start-Frame`, `X-Clip-End-Frame`, `X-Clip-Fps`.
- `GET /tracks/{global_id}/motion?limit=50`
  - Recent kinematics rows for a track (from `track_motion`).

## Media lookup
- Records should carry `video_path` and/or `video_filename`. The resolver tries, in order:
  1) `video_path` if present
  2) `video_filename` as-is
  3) `{VIDEO_ROOT}/{video_filename}`
  4) `{VIDEO_ROOT}/{video_id}.*` pattern (fallback when metadata is missing)

## Example requests
```bash
# Health
curl http://localhost:8001/

# Search
curl "http://localhost:8001/search/plates?q=ABC&limit=5"

# Vehicle details
curl http://localhost:8001/vehicles/123

# Preview (downloads JPEG)
curl -OJ http://localhost:8001/vehicles/123/preview

# Clip around the detection
curl -OJ "http://localhost:8001/vehicles/123/clip?window=60"

# Track motion history
curl "http://localhost:8001/tracks/video123:4/motion?limit=20"
```
