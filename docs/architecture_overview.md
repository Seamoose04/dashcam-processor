# Dashcam Processing Pipeline — Architecture Overview

This document gives a clean, high-level description of the entire system architecture so both developers and future contributors can quickly understand how everything fits together.

---

# 1. System Goals

The pipeline is designed to:

* Process many dashcam videos in parallel
* Use GPUs efficiently for heavy workloads (vehicle + plate detection, OCR)
* Use CPUs for lightweight tasks (plate smoothing, summary)
* Stream frames from video incrementally (not loading entire videos into RAM)
* Keep tasks/results in-memory while avoiding RAM blowups via frame_store
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
   GPU Workers
        ↓
   CPU Workers
        ↓
   Final Writer → Postgres
        ↑
Scheduler (HUD, worker monitor)
```

### Components

* **VideoReader threads** read frames and generate `VEHICLE_DETECT` tasks, obeying backpressure.
* **CentralTaskQueue** (in-memory) stores all enqueued tasks in per-category buckets.
* **GPU workers** run YOLO models and OCR (vehicle → plate → OCR).
* **CPU workers** run smoothing and summary tasks.
* **Frame store** persists frames to disk while tasks move through memory.
* **Dispatcher logic** lives inside the worker handlers; downstream tasks are created directly.
* **SchedulerProcess** is a HUD that prints queue sizes + worker states.
* **Postgres Writer** stores final plate events (`vehicles` table).

---

# 3. Task Lifecycle

Each task moves through these stages:

```
QUEUED → RUNNING → HANDLER → DOWNSTREAM TASKS
```

### Dependencies

Each task stores:

```json
{
  "payload_ref": "videoid_frameidx",
  "dependencies": ["videoid_frameidx"]
}
```

* `payload_ref` identifies the stored frame on disk.
* `dependencies` tracks all upstream frames used to produce this result.
* When a task result is handled, the dispatcher logic checks if any other tasks still depend on the frame. If not → `frame_store.delete_frame()`.

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
* Immediately call a handler to enqueue downstream CPU/GPU work

## 6.2 CPU Workers

* Dedicated to: `PLATE_SMOOTH`, `SUMMARY`
* Choose busiest CPU category
* Load lightweight resources
* Run processors, call handlers, and hand off to the next stage or final writer

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

# 7. Dispatch Flow

No separate dispatcher process now. Worker handlers directly create downstream tasks and release frame references once work is safely enqueued.

Flow per category:

* VEHICLE_DETECT → PLATE_DETECT (per vehicle)
* PLATE_DETECT → OCR (best plate)
* OCR → PLATE_SMOOTH (per plate)
* PLATE_SMOOTH → FINAL_WRITE (persist to Postgres)

Handlers also release frame references so `frame_store` can delete images when nothing else depends on them.

---

# 8. Database Architecture

Only Postgres is used for persistence. See `docs/db_schema.md` for the full table definition including video path + frame timestamp columns.

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
