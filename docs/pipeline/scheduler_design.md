# Dashcam Pipeline – Scheduler Design

## Overview

The **Scheduler** is a lightweight supervisory process responsible for monitoring worker activity, updating shared state, and providing visibility into system health.
It does *not* create tasks, perform dispatching, execute models, or perform CPU/GPU work.
Its purpose is:

* Keep track of whether workers are alive
* Detect “stuck” workers
* Expose worker category usage (for diagnostics / HUD)
* Provide heartbeat timestamps
* Help the main process determine when the system is idle and safe to shut down

The scheduler is intentionally simple, fast, and low-overhead.

---

## Responsibilities

### 1. Monitoring Worker Status

Each worker process (GPU or CPU) updates a shared `worker_status` entry:

```
{
    worker_id: {
        "pid": <int>,
        "category": <TaskCategory or None>,
        "last_heartbeat": <timestamp>
    }
}
```

The scheduler reads and interprets these.

### 2. Heartbeat & Staleness Detection

For each worker:

* If `last_heartbeat` has not updated in X seconds → mark as stale
* If a worker remains stale for too long → log a warning
* If desired, the system could implement auto-restart logic (future upgrade)

This supports debugging and resilience.

### 3. System Idle Detection

The scheduler tracks whether workers are:

* actively processing (`category` is not None)
* idle (`category` is None)

The main process uses this in combination with the queue’s backlog count to determine:

> “Is the entire system done?”

Idle + empty queues → safe shutdown.

### 4. Lightweight HUD Output

During development, the scheduler prints periodic status summaries:

* GPU backlog sizes
* CPU backlog sizes
* Per-category queue counts
* Worker category assignment
* # active vs idle workers

This helps visualize the pipeline’s load balancing.

---

## Non-Responsibilities

The scheduler deliberately does **not**:

* push tasks
* create new tasks
* validate processor output
* read frames
* run inference
* smooth plates
* write to Postgres
* manage video readers
* control shutdown events

All of those belong to other components.

The scheduler is purely a “monitor loop.”

---

## Process Lifecycle

1. The main process spawns the scheduler as a `multiprocessing.Process`.
2. The scheduler sleeps in a loop (default 1.0 seconds).
3. Each cycle:

   * Reads `worker_status`
   * Reads queue backlog
   * Logs status if needed
   * Detects stale workers
   * Updates a “scheduler heartbeat” if required
4. On shutdown:

   * The `terminate` event is set
   * Scheduler loop exits immediately
   * Process joins cleanly

Because the Scheduler never touches SQLite or frame data, its shutdown is always trivial.

---

## Data Flow

The scheduler reads four key things:

### 1. `worker_status` map

Updated continuously by all workers.

### 2. `CentralTaskQueue` backlog

Used to estimate GPU vs CPU pressure.

### 3. Shutdown flags

The scheduler respects:

* `stop`   → “stop reading new frames, but finish jobs”
* `terminate` → “stop workers immediately”

The scheduler doesn’t set these flags; it only reads them.

---

## Example Logic (human description)

* Every second:

  * Count all GPU worker categories
  * Count all CPU worker categories
  * Identify workers with missing heartbeats
  * If ALL workers idle AND queue empty → notify main thread
  * Print a summary row:

    * “3 GPU workers busy: {VEHICLE_DETECT:1, PLATE_DETECT:1, OCR:1}”
    * “5 CPU workers busy: {PLATE_SMOOTH:3, SUMMARY:2}”
  * Mark any slow workers (e.g., >10s with no heartbeat)

The key point:
The scheduler helps **balance** and **understand** the pipeline, but never **controls** it.

---

## Why the Scheduler Is Lightweight

Design goals:

* Must not slow workers
* Must not block or lock the queue
* Must be safe to kill at any time
* Must remain transparent and non-intrusive

It acts as an overseer, not a manager.

---

## Interactions With Other Components

### With Workers

Workers write to shared state:

```
worker_status[id]["category"] = TaskCategory
worker_status[id]["last_heartbeat"] = time.time()
```

Scheduler reads but never writes.

### With Dispatcher

No direct interaction.
Both read from SQLite, but with separate connections.

### With VideoReader

No interaction.

### With Main Process

The Scheduler helps the main process decide when the system has finished.

---

## Future Extensions

These are optional enhancements not yet implemented:

* Auto-restart stuck workers
* Dynamic allocation of GPU/CPU workers based on backlog
* Integrating a small HTTP server to show worker stats live
* Export Prometheus metrics
* Dispatcher/Scheduler event timelines

---

## Summary

The Scheduler is a simple, low-overhead monitor whose job is:

* Watch the workers
* Report worker activity
* Detect idle states
* Assist shutdown decisions

It does **no processing**, **no dispatching**, and **no task generation**.
Its minimalism is intentional — reliability through simplicity.

---
