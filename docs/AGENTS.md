# Dashcam Pipeline — Agents

This document lists every long-running agent (process or thread) in the pipeline, what it owns, and how it cooperates with the others. Use it to quickly find where responsibilities live when debugging or adding new behavior.

```
main.py (process)
├─ SchedulerProcess (process)
├─ VideoReader threads (per input video)
├─ GPUWorkerProcess[N] (processes)
└─ CPUWorkerProcess[M] (processes)
```

---

# 1) Main Process — Orchestrator (`main.py`)

* **Boot:** reads env config (`NUM_GPU_WORKERS`, `NUM_CPU_WORKERS`, `NUM_VIDEO_READERS`, backlog limits), builds shared `Manager` objects, initializes `frame_store`, `CentralTaskQueue`, and the worker status map.
* **Spawns:** Scheduler, video reader threads, GPU workers, CPU workers.
* **Control plane:** installs SIGINT/SIGTERM handler; sets the `stop` event when Ctrl+C arrives and logs a backlog snapshot; polls backlog + worker_status to decide when work is finished.
* **Shutdown sequence:** sets `stop` (pause readers), waits for backlog to drain or timeout, sets `terminate` (workers/scheduler exit loops), joins processes, and forces any stragglers.

---

# 2) VideoReader Threads (`pipeline/video_reader.py`)

* **Role:** ingest videos frame-by-frame, push `VEHICLE_DETECT` tasks.
* **Backpressure:** pauses when GPU or CPU backlog exceeds configured limits; resumes automatically when queues recover.
* **Frame handling:** saves each frame to `frame_store`, tracks `payload_ref` + `dependencies`, enqueues tasks with those references.
* **Exit conditions:** finishes when the video ends or when `stop` is set; releases OpenCV capture on exit.

---

# 3) GPU Workers (`pipeline/workers/gpu_worker.py`)

* **Scope:** categories `VEHICLE_DETECT`, `PLATE_DETECT`, `OCR`.
* **Scheduling:** picks the busiest GPU category each loop; loads model/resource on category switch.
* **Work loop:** pop task → run processor → call handler to enqueue downstream CPU/GPU work → release frame refs via `frame_store.release_refs`.
* **Visibility:** updates `worker_status` with PID, active category, and heartbeat for the scheduler/HUD.
* **Shutdown:** ignores SIGINT/SIGTERM directly; exits when `terminate` is set.

---

# 4) CPU Workers (`pipeline/workers/cpu_worker_mp.py`)

* **Scope:** categories `VEHICLE_TRACK`, `PLATE_SMOOTH`, `SUMMARY`, `FINAL_WRITE`.
* **Scheduling:** chooses busiest CPU category; loads lightweight resources on switch (tracker, smoother, writer, etc.).
* **Work loop:** pop task → run processor → call handler (e.g., enqueue FINAL_WRITE or write to Postgres) → release dependencies.
* **Visibility:** same heartbeat contract as GPU workers via `worker_status`.
* **Shutdown:** also ignores SIGINT/SIGTERM; exits when `terminate` is set.

---

# 5) Scheduler Process (`pipeline/scheduler.py`)

* **Role:** monitor-only agent; never executes tasks or models.
* **Inputs read:** `worker_status` map, queue backlog counts, shutdown flags.
* **Outputs:** periodic HUD logs, stale-worker warnings, idle detection to help main decide when the system is done.
* **Shutdown:** loop exits when `terminate` is set; safe to kill anytime because it holds no resources.

---

# 6) Shared Coordination

* **Events:** `stop` tells producers (readers) to halt; `terminate` tells workers + scheduler to exit their loops. Main raises them in that order.
* **Queue:** `CentralTaskQueue` is the handoff point for all agents; workers choose categories based on backlog, readers respect soft/hard limits when pushing.
* **Frame lifecycle:** `frame_store.add_refs` on enqueue, `release_refs` on handler completion; frames are deleted once no tasks depend on them.
* **Heartbeat map:** `worker_status` lives in a `Manager().dict()` and is the single source of truth for which agent is active on which category.

---

# 7) Operational Knobs

Key environment variables:

```
NUM_GPU_WORKERS=2
NUM_CPU_WORKERS=4
NUM_VIDEO_READERS=2
MAX_GPU_BACKLOG=8
MAX_CPU_BACKLOG=16
QUEUE_SOFT_LIMIT=64
QUEUE_HARD_LIMIT=128
```

Tune counts and limits based on hardware; the agents above will auto-balance work according to the queue backlogs.
