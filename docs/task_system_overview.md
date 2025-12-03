# Task System Overview

This document describes the unified task model used across all devices in the distributed dashcam-processing pipeline. The goal is to ensure:

* Deterministic, reproducible work
* Safe interruption and recovery
* No race conditions
* No duplicated work
* Clean separation of responsibilities across devices
* Simple state machine (only `pending` and `complete`)
* Support for both local (ephemeral) and remote (published) sub‑tasks
* A predictable, DAG-like structure without circular dependencies

---

# 1. Core Principles

### 1.1 Pull-Based Distributed Execution

All devices pull tasks from the central server. The server never pushes tasks to devices.

This ensures:

* Devices can go offline safely
* Devices come back online without special synchronization
* Server does not need to track device state
* Work distribution scales horizontally by simply adding more devices

---

# 2. Task States

The system uses **only two persistent states**:

* `pending`
* `complete`

There is **no** `in_progress` or `claimed` state.

Reasoning:

* A task can only be pulled by one device at a time
* Retrying a task produces identical results
* Work is idempotent and restartable
* Local tasks are ephemeral and cleared on reboot
* Tasks are only marked `complete` when fully done

This keeps the global state machine extremely small, easy to reason about, and resistant to crashes.

---

# 3. Task Execution Flow

Each device operates as follows:

1. Pull oldest `pending` task of a type it is eligible to run
2. Perform the task, spawning **local tasks** as needed
3. Once all local tasks finish, determine if any **remote tasks** need to be created
4. If remote tasks are required:

   * Publish them to the central server
5. Mark the current task as `complete`
6. Pull next pending task

This flow guarantees that:

* Remote tasks are only created *once per parent task*
* Remote tasks are only created *after* the parent task succeeds
* No duplicated remote tasks can occur

---

# 4. Local Tasks

Local tasks:

* Are created only by the device currently working on a parent task
* Are never stored in the central database
* Must complete before the parent task is completed
* Are higher priority than pulling new remote tasks
* Are cleared immediately on interruption or reboot
* Exist only as a private queue on the device

**Examples:**

* Decoding frames
* Temporary caching
* Jetson preprocessing steps
* 4090 temporary intermediate crops

Local tasks prevent the need for multi-step remote state. They are simply internal prerequisite atomic work units.

---

# 5. Remote Tasks

A remote task is a follow-up task that must be executed by a *different device type* after the current parent task completes.

Rules:

* Remote tasks are **NOT** published during parent processing
* Remote tasks are **only** published at the end, *after* all local tasks are complete
* Publishing occurs atomically with marking the parent `complete`
* Since a task can only be completed once, remote tasks can only be generated once

**Examples:**

* Jetson completes preprocessing → publishes "GPU heavy processing" task for the 4090
* 4090 completes heavy processing → publishes "archival processing" task for the main server or shed NAS

This forms a clean directed acyclic graph (DAG) of tasks.

---

# 6. Interruption and Recovery

The pipeline is designed around the assumption that devices will be interrupted.

## 6.1 Interruption Mid-Task

If a device is interrupted:

* All local tasks are immediately discarded
* No parent task is ever marked `complete`
* No remote tasks are published
* State in DB remains `pending`
* On reboot, device pulls the same task and recomputes from scratch

This is safe because all work is deterministic.

## 6.2 Example Failure/Recovery Cycle

```
1. 4090 pulls Task A
2. 4090 creates local tasks (L1, L2, L3)
3. 4090 completes L1 and L2
4. Power loss occurs
5. 4090 reboots, clears local tasks
6. Task A still pending in DB
7. 4090 pulls Task A again
8. This time finishes fully
9. Publishes remote Task B
10. Marks Task A complete
```

This is correct behavior and guarantees no duplication.

---

# 7. No Circular Task Graphs

Task types are strictly partitioned:

* Dashcam ingestion → Jetson preprocessing → 4090 heavy processing → server finalize → shed archival

No device ever generates a remote task that routes back to the same type of device.

Therefore, cycles are impossible.

---

# 8. Device Eligibility for Task Types

Each task type defines which device or device class may execute it.

Example (simplified):

* `ingest` → server
* `preprocess` → Jetson+Coral
* `heavy_process` → 4090
* `finalize` → server
* `archive` → shed NAS

This makes scheduling trivial.

---

# 9. Priority Rules

1. **Local tasks have highest priority**
2. **If local queue is empty**, pull next remote task from server
3. **Pending tasks are always processed oldest-first**

This ensures:

* No starvation
* FIFO correctness
* Discrete checkpoints

---

# 10. Data Handling Semantics

Each task knows exactly what data it needs to consume and where that data resides.

The central DB entry includes:

* Input paths (NAS, Jetson-preproc folder, server cache)
* Output paths
* Final desired outputs

Each device reads from the data sources specified by its task.

Temporary data is always local to the device and discarded on completion or interruption.

---

# 11. Why This System Works So Well

* **Crash-safe**: No possible corrupted state
* **Deterministic**: Re-running tasks yields identical results
* **Scalable**: Add more devices without redesign
* **Simple**: Only two states to manage
* **Efficient**: Work always flows downhill toward completion
* **Clean DAG**: No cycles or re-ordering concerns
* **Decentralized execution**: Devices orchestrate themselves
* **Minimal DB writes**: Saves performance on small NAS/server hardware

---

# 12. Summary

This task system is an extremely reliable, minimal-overhead workflow engine tailored to your hardware and processing pipeline. It:

* Ensures each task runs exactly once
* Allows infinite retries without special handling
* Guarantees remote tasks are published exactly once
* Safely handles interruptions on any device
* Requires almost no coordination logic on the server
* Allows each device to operate autonomously

It is the ideal control layer for the distributed dashcam-processing architecture.
