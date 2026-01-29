# Architecture Overview

This document provides a high-level, end-to-end description of how every device in the pipeline interacts to process dashcam footage into a finalized, searchable dataset served through a WebUI. It ties together ingestion, preprocessing, heavy processing, archival, and the distributed task system used by all devices.

This is the "read first" guide to the entire system.

---
# 1. System Goals

The architecture is designed to:
* Automatically ingest dashcam videos as soon as you arrive home
* Reliably transform raw footage into searchable, labeled, GPS-aligned data
* Minimize storage usage through multi-stage de-resolution and selective retention
* Utilize each device for the tasks it is best suited for
* Remain fully resilient to interruptions, restarts, or power loss
* Scale naturally as more hardware is added
* Provide a simple, intuitive WebUI experience

---
# 2. High-Level Data Flow

The overall pipeline progresses through distinct phases:

```
Dashcam → Indoor NAS → 4090 Machine → Main Server → Shed NAS → WebUI
```

Each stage transforms the data and spawns new tasks to progress the workflow.

### 2.1 Summary of Device Roles

* **Dashcam:** Records raw video files
* **Indoor NAS:** First storage layer, ingestion gateway
* **4090 Machine:** Heavy GPU processing (YOLO, OCR, GPS alignment)
* **Main Server:** Task coordinator + state machine host
* **Shed NAS:** Final archival storage for WebUI media
* **WebUI:** Interactive interface served from archived data

### 2.2 Artifact Flow (authoritative locations)

```
Stage            | Stored artifacts                      | Lives on
-----------------|---------------------------------------|-----------------------
Dashcam          | Raw MP4 segments                       | Dashcam SD
Indoor NAS       | Raw videos                            | Indoor NAS (/videos/raw)
4090 Machine     | Heavy outputs (detections/crops temp) | Indoor NAS (/videos/heavy_output) until finalized
Main Server      | Finalized metadata (detections, GPS)   | Main Server DB (authoritative)
Shed NAS         | Final media (de-res video + plate crops)| Shed NAS (/archive/<video_id>/)
WebUI            | Reads metadata from Main Server, media from Shed NAS | N/A (consumer)
```

---
# 3. Core Concepts

### 3.1 Tasks
Everything in the pipeline is formalized as a **task**, defined and stored on the main server. Tasks are always:

* Pulled by devices (never pushed)
* Atomic
* Deterministic
* Crash-safe

Devices communicate progress only by marking tasks `complete`.

### 3.2 Local Tasks
Each device may spawn its own local sub-tasks. These:
* Are *never* published to the server
* Must finish before the parent task completes
* Are deleted immediately on interruption or reboot

### 3.3 Remote Tasks
If completing a task requires follow-up work from another device type, the device publishes new tasks to the server **only after** it finishes its own work.

---
# 4. Device-by-Device Overview

This section summarizes what each device contributes.

## 4.1 Dashcam
* Records high-resolution video files
* Stores them on the SD card with timestamps
* May include GPS metadata
* Exposes files via Wi-Fi or removable storage

## 4.2 Indoor NAS
* Runs `viofosync` to automatically pull dashcam videos
* Stores videos in `/videos/raw/<trip>/`
* Notifies the main server by inserting a new ingestion task
* Provides network storage for Jetson and 4090
* Holds raw videos until processing is complete

## 4.3 4090 Machine
* Pulls heavy GPU tasks
* Performs:
  * Full-resolution YOLO detection
  * Full-resolution OCR
  * GPS timestamp alignment
  * Confidence aggregation
  * Generation of full-res plate crops
  * Selection of best frames
* Only keeps temporary data locally
* Publishes remote archival tasks when finished

## 4.4 Main Server
* Central task scheduler and source-of-truth database
* Holds all `pending` and `complete` tasks
* Does not push tasks; devices pull them autonomously
* Manages retries implicitly (pending tasks repeat on crash)
* Performs its own light tasks (ingestion, finalization)
* Orchestrates communication without tight coupling

## 4.5 Shed NAS
* Long-term archival storage
* Receives de-res videos (720p/540p)
* Stores high-res plate crops
* Acts as the backend data provider for the WebUI
* Stores metadata summaries from the server

## 4.6 WebUI
* Reads metadata from the main server
* Reads media from the Shed NAS
* Treats the main server as the single source of truth for metadata; Shed NAS serves media only
* Displays:
  * Maps
  * Plate timelines
  * Video browser
  * Frame thumbnails
  * Filter/search tools

---
# 5. End-to-End Lifecycle
This is the medium-level flow of a single video:

1. **Dashcam records video**
2. **Indoor NAS pulls video via `viofosync`**
3. NAS triggers a new ingestion task on the main server
4. **4090 Machine pulls heavy-processing task**, runs YOLO + OCR + GPS alignment
5. 4090 publishes archival task
6. **Server finalizes**, sends archival data to Shed NAS
7. **Shed NAS stores** the archived outputs
8. **WebUI displays** detections, crops, GPS route, timeline

---
# 6. Resilience to Interruptions
The architecture is explicitly designed to handle crashes without special logic.

* If a device loses power, local tasks are discarded
* Parent tasks remain `pending`
* Upon restart, devices simply re-pull those tasks
* No task can be duplicated because remote tasks only publish after successful completion
* The main server never tracks device state, so restarts have zero global impact

---
# 7. Benefits of This Architecture
* **Highly reliable:** No risk of corruption or duplicated work
* **Optimized for your hardware:** Each device does exactly what it’s best at
* **Extremely low overhead:** Minimal locking, tiny DB writes, simple state transitions
* **Naturally scalable:** Just add devices; they pull tasks automatically
* **Efficient storage:** Full-res retained only until processing is complete
* **Clear separation of concerns:** Ingestion → Heavy Processing → Archival → UI
* **Easy debugging:** Tasks form a clean chain, easy to trace

---
# 8. Summary
This architecture provides a robust, interruption-safe, distributed workflow for processing dashcam videos end-to-end. Every device participates using a unified task model, and the system flows cleanly through ingestion, heavy GPU work, final archival storage, and UI display.

This overview serves as the backbone for the detailed device-specific documents that follow.
