# Main Server

The main server is the **central coordinator** of the entire distributed dashcam-processing pipeline. It holds the source-of-truth database, manages all pipeline tasks, performs certain lightweight processing steps, and orchestrates the overall workflow without ever directly controlling or pushing work to other devices.

This machine functions as the pipeline's brain and authoritative state keeper.

---

# 1. Responsibilities

The main server is responsible for:

* Maintaining the global task database
* Deciding which tasks exist and when they are created
* Representing the canonical state of every video in the system
* Storing ingestion metadata
* Persisting finalized metadata (detections, GPS, plate timelines) for WebUI queries
* Handling light processing tasks (e.g., ingest validation, finalization)
* Serving as the communication hub between devices
* Ensuring the system remains resilient through interruptions

It does **not**:

* Perform heavy GPU work
* Push tasks to other devices
* Manage local sub-tasks

---

# 2. Task Database (Source of Truth)

The heart of the server is a small, durable database storing a list of tasks and their associated metadata.

Key properties:

* Tasks only have **two persistent states**: `pending` and `complete`
* Tasks specify which device class is eligible to execute them
* All worker devices pull tasks from this DB
* Retry behavior is implicit: a task remains `pending` until a device completes it

### Task Fields (Conceptual)

* `task_id`
* `task_type`
* `video_id`
* `state` = `pending` or `complete`
* `inputs` (json object, array of: { `device`, `path`, `type?` })
* `created_at`
* `completed_at`

This DB is intentionally minimal to maximize reliability and debuggability.

---

# 3. Device Interaction Model

### Pull-Based Workflow

Devices (Jetson, 4090, etc.) independently:

1. Query the server for the oldest pending task they can execute
2. Pull it
3. Perform local work
4. Optionally generate remote tasks
5. Mark the task as complete

The server never sends tasks and never needs to know device state.

### Why This Works

* No locking mechanisms
* No race conditions
* Even if a device crashes mid-task, the DB remains stable
* Once the device restarts, it will simply re-pull the same task

---

# 4. Task Lifecycle

Every task in the pipeline goes through a simple, robust lifecycle:

1. **Creation** — triggered by ingestion or upstream tasks
2. **Pending** — waiting to be pulled by the correct device
3. **Execution** — device performs work (local tasks included)
4. **Completion** — device marks the task complete and publishes any new tasks

No partial states and no need for in-progress tracking.

---

# 5. Server-Side Responsibilities

Although heavy work is offloaded to other devices, the main server still handles a handful of essential tasks:

## 5.1 Ingestion Processing

* Detects new videos synced to the Indoor NAS
* Creates the initial ingestion task
* Extracts basic metadata (filename, timestamp)
* Validates video file structure

## 5.2 Task Creation for Downstream Devices

* When ingestion completes, the server creates a preprocessing task for the Jetson
* When heavy processing completes, the server creates a finalization or archival task

## 5.3 Finalization Tasks

These tasks may include:

* Ensuring archival outputs exist
* Updating global metadata for WebUI
* Removing temporary directories on server storage

## 5.4 Light Utility Tasks

* Metadata cleanup
* Index maintenance for WebUI
* Data shuffling and reorganization

---

# 6. Storage Responsibilities

The main server stores:

* The global task database
* Lightweight metadata and summaries
* Finalized detection/GPS metadata (authoritative source for the WebUI)
* Temporary intermediate output (only small, non-video data)

It does **not** store:

* Raw video files (Indoor NAS responsibility)
* Jetson preprocessing output (Jetson local storage)
* Heavy GPU intermediate data (4090 local storage)
* Final archived media (Shed NAS responsibility)

Server storage remains minimal and predictable.

---

# 7. Failure & Recovery Behavior

The main server's role is specifically designed to be resilient:

### In Case of Device Failure

* Jetson or 4090 crashes do not affect the server
* Their tasks remain `pending`
* Once the device restarts, it resumes normally

### In Case of Server Failure

* Task DB is stored durably
* On restart, devices can continue to pull tasks as if nothing happened

### In Case of NAS Unavailability

* Tasks requiring NAS paths simply re-try later
* No corruption occurs

---

# 8. Scalability & Extensibility

The server’s design makes it extremely easy to scale:

* Adding another Jetson or another 4090 requires **no changes** to the server
* Additional device types can be added by simply adding new task types
* New pipeline stages can be introduced as new tasks

Work distribution remains simple and reliable.

---

# 9. Summary

The main server is the authoritative controller and state manager for the entire pipeline. By relying on a minimalistic two-state task system and a clean pull-based model, it avoids complexity, remains fully resilient to failures, and offers a robust, extensible foundation for all aspects of the distributed workflow.

It coordinates devices without micromanaging them, ensuring that each machine does only what it is best at, with maximum reliability and minimum overhead.
