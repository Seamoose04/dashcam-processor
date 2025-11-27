# Database Schema — Dashcam Pipeline

This pipeline no longer uses a local SQLite task DB. All task orchestration is in-memory (queues + shared state) and only **Postgres** is used for final, queryable results.

---

# 1. Storage Overview

* **In-memory**: task queue, worker status, and frame references (frames live on disk under `frame_store/`).
* **Postgres (`dashcam_final`)**: persistent plate events ready for search/analytics.

---

# 2. Postgres Schema (`dashcam_final`)

Currently persisted tables:
- `vehicles` (license plate events; now also carries `global_id` when tracking is available)
- `tracks` (one row per detector track; provides `global_id`)
- `track_motion` (per-frame motion for each track)

## 2.1 `vehicles` Table

### Schema

```
CREATE TABLE vehicles (
    id SERIAL PRIMARY KEY,
    global_id TEXT,                     -- "{video_id}:{track_id}" when tracking is available
    track_id INTEGER,
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    video_ts_frame INTEGER,
    video_path TEXT,
    video_filename TEXT,
    ts TIMESTAMPTZ NOT NULL,

    final_plate TEXT NOT NULL,
    plate_confidence REAL,

    car_bbox JSONB NOT NULL,
    plate_bbox JSONB NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Field Explanations

| Column               | Meaning                                                      |
| -------------------- | ------------------------------------------------------------ |
| **id**               | Unique row identifier                                        |
| **global_id**        | Optional global track key (`{video_id}:{track_id}`)          |
| **track_id**         | Optional stable vehicle track ID (from detector)             |
| **video_id**         | Short identifier (basename without extension)                |
| **frame_idx**        | Frame number where this plate was observed                   |
| **video_ts_frame**   | Video-relative timestamp expressed as a frame number         |
| **video_path**       | Full path to the source video (as seen by the reader)        |
| **video_filename**   | Video filename with extension                                |
| **ts**               | Processing timestamp (UTC) — set when the row is written     |
| **final_plate**      | Smoothed OCR result                                          |
| **plate_confidence** | Model confidence associated with `final_plate`               |
| **car_bbox**         | JSONB bounding box of car                                    |
| **plate_bbox**       | JSONB bounding box of license plate                          |
| **created_at**       | Insertion timestamp                                          |

### Notes

* `video_ts_frame` gives a deterministic position in the video even when FPS metadata is missing; `frame_idx` is kept for backward compatibility.
* `ts` remains the processing time; supply a custom timestamp in the final-write payload if you prefer video-time instead.

---

# 3. Data Flow (high level)

```
VideoReader → CentralTaskQueue → GPU/CPU workers → Final writer → Postgres.vehicles
```

Frames are kept on disk (`frame_store/`); metadata is passed through task payloads and written only when the final writer runs.

---

# 4. Future Extensions

Potential additions:

* `tracks` table (per-vehicle tracking)
* `alerts` table (plate of interest)
* `frame_events` table (all objects, not just plates)
* `video_metadata` table
* TimescaleDB/PG indexes for temporal queries

The current schema is intentionally lean; add new tables as new downstream consumers appear.

---

# 3. Global ID / Tracking Tables

To support CPU-side motion tracking and cross-table joins, we introduce a `global_id` per detector track (`{video_id}:{track_id}`).

## 3.1 `tracks` Table (one row per track)

```
CREATE TABLE tracks (
    id SERIAL PRIMARY KEY,
    global_id TEXT UNIQUE NOT NULL,        -- "{video_id}:{track_id}"
    video_id TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    frame_idx INTEGER,                     -- optional convenience; first seen frame
    first_frame_idx INTEGER NOT NULL,
    video_ts_frame INTEGER,
    video_ts_ms DOUBLE PRECISION,
    video_path TEXT,
    video_filename TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Use this as the anchor for joins across other per-track properties.

## 3.2 `track_motion` Table (per-frame kinematics)

```
CREATE TABLE track_motion (
    id SERIAL PRIMARY KEY,
    global_id TEXT NOT NULL REFERENCES tracks(global_id),
    track_id INTEGER,
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    video_ts_frame INTEGER,
    video_ts_ms DOUBLE PRECISION,
    bbox JSONB,
    vx DOUBLE PRECISION,
    vy DOUBLE PRECISION,
    speed_px_s DOUBLE PRECISION,
    heading_deg DOUBLE PRECISION,
    age_frames INTEGER,
    conf REAL,
    video_path TEXT,
    video_filename TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Join `track_motion` with `vehicles` (license plates) via `global_id` to answer queries such as “frames where plate X was moving toward the camera.”
