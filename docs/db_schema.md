# Database Schema — Dashcam Pipeline

This document describes the complete database schema for the pipeline, covering both **SQLite** (internal task orchestration) and **Postgres** (final results). It includes table definitions, field meanings, and design rationale.

---

# 1. Overview

The system uses **two separate databases**, each serving a different purpose:

## **SQLite (`pipeline.db`)**

* Local, fast, lightweight
* Stores tasks + results
* Coordinates dispatcher logic
* Supports dependency-based frame cleanup
* Recreated every pipeline run

## **Postgres (`dashcam_final`)**

* Permanent storage
* Stores final vehicle events
* Optimized for search and querying

---

# 2. SQLite Schema

SQLite is used for internal pipeline operations only.

It contains two tables:

* `tasks`
* `results`

These tables **reflect the full processing graph** of all frames for all videos.

---

## 2.1 `tasks` Table

### Schema

```
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    payload TEXT,        -- JSON: {"payload_ref": ...} or other small refs
    priority INTEGER,
    video_id TEXT,
    frame_idx INTEGER,
    track_id INTEGER,
    meta TEXT,           -- JSON: includes payload_ref, car_bbox, plate_bbox, dependencies, etc.
    dependencies TEXT,   -- JSON: list of payload_refs
    status TEXT           -- 'queued' | 'done'
);
```

### Field Explanations

| Column           | Meaning                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| **id**           | Unique task ID, used as primary link between workers ↔ dispatcher       |
| **category**     | TaskCategory (vehicle_detect, plate_detect, ocr, plate_smooth, summary) |
| **payload**      | JSON-encoded small reference (actual frame lives on disk)               |
| **priority**     | Priority (unused now but allows future scheduling control)              |
| **video_id**     | Identifier of video where frame originated                              |
| **frame_idx**    | Frame number within the video                                           |
| **track_id**     | Optional future use (tracking per vehicle)                              |
| **meta**         | Everything else needed by workers, encoded as JSON                      |
| **dependencies** | JSON list of all upstream frame references                              |
| **status**       | 'queued' until worker finishes, then 'done'                             |

### Notes

* Task objects are always recreated from DB when dispatched.
* `payload` is *not* the raw frame — only a lightweight pointer.
* Workers write results back into SQLite, allowing dispatcher to poll.

---

## 2.2 `results` Table

### Schema

```
CREATE TABLE results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    result TEXT,      -- JSON result object
    handled INTEGER DEFAULT 0
);
```

### Field Explanations

| Column      | Meaning                                                 |
| ----------- | ------------------------------------------------------- |
| **id**      | Unique result ID                                        |
| **task_id** | Links to a task in the `tasks` table                    |
| **result**  | JSON-encoded result produced by worker                  |
| **handled** | 0 = dispatch not yet processed this result, 1 = handled |

### Notes

* Dispatcher repeatedly fetches rows with `handled = 0`.
* After processing, dispatcher sets `handled = 1`.
* Results remain in DB only for trace/debug; can be pruned later.

---

## 2.3 Dependency Cleanup Query

SQLite also enables frame cleanup through this query:

```sql
SELECT COUNT(*)
FROM tasks t
LEFT JOIN results r ON r.task_id = t.id
WHERE t.id != ?
  AND t.dependencies LIKE ?
  AND (
        t.status != 'done'
        OR (r.id IS NOT NULL AND r.handled = 0)
      );
```

If count == 0 → safe to delete frame.

---

# 3. Postgres Schema (`dashcam_final`)

This database stores **only final results** that are ready for long-term querying.

It contains one core table so far:

* `vehicles`

---

## 3.1 `vehicles` Table

### Schema

```
CREATE TABLE vehicles (
    id SERIAL PRIMARY KEY,
    track_id INTEGER,
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    final_plate TEXT NOT NULL,
    plate_confidence FLOAT NOT NULL,
    car_bbox JSONB NOT NULL,
    plate_bbox JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Field Explanations

| Column               | Meaning                                            |
| -------------------- | -------------------------------------------------- |
| **id**               | Unique row identifier                              |
| **track_id**         | Optional stable vehicle track ID (from detector)   |
| **video_id**         | Source video identifier                            |
| **frame_idx**        | Frame number where this plate was observed         |
| **ts**               | Timestamp of event (frame time or processing time) |
| **final_plate**      | Smoothed OCR result                                |
| **plate_confidence** | Model confidence associated with `final_plate`     |
| **car_bbox**         | JSONB bounding box of car                          |
| **plate_bbox**       | JSONB bounding box of license plate                |
| **created_at**       | Insertion timestamp                                |

---

# 4. Relationships Between Databases

| SQLite                             | Postgres                           |
| ---------------------------------- | ---------------------------------- |
| Stores tasks & intermediate states | Stores final, authoritative events |
| Temporary, recreated each run      | Persistent, lives across runs      |
| Used for pipeline logic            | Used for queries & analytics       |
| Everything is JSON inside          | Strongly typed columns             |

### Flow

```
SQLite.tasks → SQLite.results → Dispatcher → Postgres.vehicles
```

---

# 5. Rationale for Two Databases

### SQLite is ideal for:

* High write rate
* No schema migrations
* Local process coordination
* Fast access from many processes
* Temporary pipeline state

### Postgres is ideal for:

* Searching/filtering (date ranges, LIKE queries)
* Full text search on plates
* JSONB indexing
* Keeping millions of rows permanently
* Joining with other metadata later

This hybrid approach gives you the best of both worlds.

---

# 6. Future Schema Extensions

### Potential additions:

* `tracks` table (per-vehicle tracking)
* `alerts` table (plate of interest)
* `frame_events` table (all objects, not just plates)
* `video_metadata` table
* Spatial indexing for bounding boxes
* TimescaleDB for temporal plate histories

All can be integrated with the existing flow.

---

# 7. Summary

This schema design is optimized for:

* High-throughput ingestion
* Efficient multi-worker processing
* Clean, lossless shutdown
* Fast, expressive querying
* Historical retention of final events only

SQLite handles orchestration; Postgres handles long-term storage.

---
