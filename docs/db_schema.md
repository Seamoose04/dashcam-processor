# Database Schema — Dashcam Pipeline

This pipeline no longer uses a local SQLite task DB. All task orchestration is in-memory (queues + shared state) and only **Postgres** is used for final, queryable results.

---

# 1. Storage Overview

* **In-memory**: task queue, worker status, and frame references (frames live on disk under `frame_store/`).
* **Postgres (`dashcam_final`)**: persistent plate events ready for search/analytics.

---

# 2. Postgres Schema (`dashcam_final`)

Only one table is persisted today: `vehicles`.

## 2.1 `vehicles` Table

### Schema

```
CREATE TABLE vehicles (
    id SERIAL PRIMARY KEY,
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
