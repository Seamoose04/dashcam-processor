# Dashcam Processing Pipeline — Architecture Overview

This document gives a clean, high-level description of the entire system architecture so both developers and future contributors can quickly understand how everything fits together.

---

# 1. System Goals

The pipeline is designed to:

* Process many dashcam videos in parallel
* Use GPUs efficiently for heavy workloads (vehicle + plate detection, OCR)
* Use CPUs for lightweight tasks (plate smoothing, summary)
* Stream frames from video incrementally (not loading entire videos into RAM)
* Persist tasks + results in SQLite
* Write final plates and metadata to Postgres
* Coordinate multiple worker processes cleanly
* Support graceful shutdown without leaving processes hanging

---

# 2. High-Level Architecture

```
VideoReader Threads
        ↓
   CentralTaskQueue
        ↓
   GPU Workers  ←→ SQLite (tasks + results)
        ↓
   CPU Workers  ←→ SQLite (tasks + results)
        ↓
   Dispatcher → (final results) → Postgres
        ↑
Scheduler (HUD, worker monitor)
```

### Components

* **VideoReader threads** read frames and generate `VEHICLE_DETECT` tasks, obeying backpressure.
* **CentralTaskQueue** (in-memory) stores all enqueued tasks in per-category buckets.
* **GPU workers** run YOLO models and OCR (vehicle → plate → OCR).
* **CPU workers** run smoothing and summary tasks.
* **SQLiteStorage** is the source of truth for:

  * tasks table
  * results table
  * dependency-based cleanup
* **DispatcherProcess** reads unhandled results from SQLite and schedules downstream tasks.
* **SchedulerProcess** is a HUD that prints queue sizes + worker states.
* **Postgres Writer** stores final plate events (`vehicles` table).

---

# 3. Task Lifecycle

Each task moves through these stages:

```
QUEUED → RUNNING → DONE → (result saved) → DISPATCHED → DOWNSTREAM TASKS
```

### Dependencies

Each task stores:

```json
{
  "payload_ref": "videoid_frameidx",
  "dependencies": ["videoid_frameidx"]
}
```

* `payload_ref` identifies the stored frame.
* `dependencies` tracks all upstream frames used to produce this result.
* When a task result is handled, the dispatcher checks if any other tasks still depend on the frame. If not → `frame_store.delete_frame()`.

---

# 4. VideoReader Architecture

Each `VideoReader`:

* Streams frames from one video
* Obeys backpressure from GPU/CPU queues
* Stores frame in `frame_store`
* Generates one `VEHICLE_DETECT` task per frame
* Stops when `stop` is set or video ends

This runs on a separate thread per video. All readers share the same queue.

---

# 5. CentralTaskQueue

A multiprocess-safe structure with:

* `push(task_id, task)`
* `pop(category)`
* `backlog(category)`
* `total_backlog()`

Each category has its own FIFO bucket. Workers pop from their categories only.

---

# 6. Workers

## 6.1 GPU Workers

* Dedicated to: `VEHICLE_DETECT`, `PLATE_DETECT`, `OCR`
* Choose busiest GPU category
* Load YOLO / OCR models per-category
* Run processors (`process_vehicle`, `process_plate`, `process_ocr`)
* Write results to SQLite

## 6.2 CPU Workers

* Dedicated to: `PLATE_SMOOTH`, `SUMMARY`
* Choose busiest CPU category
* Load lightweight resources
* Write results to SQLite

### Worker Status

A `Manager().dict()` tracks:

```
worker_status[worker_id] = {
    "pid": ...,
    "category": "ocr",
    "last_heartbeat": time.time()
}
```

Used by Scheduler HUD.

---

# 7. Dispatcher

Runs every ~0.2 seconds.

Steps:

1. `fetch_unhandled_results()` from SQLite
2. For each result, call category-specific handler:

   * VEHICLE_DETECT → PLATE_DETECT
   * PLATE_DETECT → OCR
   * OCR → PLATE_SMOOTH
   * PLATE_SMOOTH → SUMMARY → Postgres
3. Mark result handled
4. Check dependencies and delete frames

Dispatcher is the heart of flow control.

---

# 8. Database Architecture

## SQLite (`pipeline.db`)

* **tasks** table
* **results** table
* Dependency-based cleanup
* One SQLite connection per process

## Postgres (`dashcam_final`)

`vehicles` table:

```
id SERIAL PRIMARY KEY
video_id TEXT
frame_idx INTEGER
ts TIMESTAMPTZ
final_plate TEXT
plate_confidence FLOAT
car_bbox JSONB
plate_bbox JSONB
created_at TIMESTAMPTZ DEFAULT now()
```

Used for query/search later.

---

# 9. Shutdown Architecture

Two global events:

* **stop** → stop producing new tasks (VideoReaders exit)
* **terminate** → workers exit immediately at the next iteration

Shutdown sequence:

1. User presses Ctrl+C → sets `stop`
2. VideoReaders stop enqueueing new tasks
3. Main loop waits for backlog to reach zero
4. Sets `terminate`
5. Workers exit gracefully
6. Dispatcher & Scheduler stop

---

# 10. Future Improvements

* Global tracking layer for multi-worker consistent track IDs
* GPU batch processing
* Distributed cluster execution
* Hybrid CPU/GPU load balancing
* Auto video rotation & preprocessing

---

# End

This is the top-level architectural map of the full dashcam pipeline.
