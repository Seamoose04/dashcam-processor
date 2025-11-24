# Dashcam Processing Pipeline — Task Flow

This document explains the end-to-end flow of a single frame through the entire pipeline—how tasks move from creation to completion, how workers interact with the queue, and how results propagate through the system.

Use this to understand *exactly* what happens after a frame enters the system.

---

# 1. Overview of Task Categories

The pipeline uses a fixed set of `TaskCategory` values:

## GPU Categories

* **VEHICLE_DETECT** — YOLO vehicle detector
* **PLATE_DETECT** — YOLO plate detector (car ROI → plate ROI)
* **OCR** — text extraction from plate ROI

## CPU Categories

* **PLATE_SMOOTH** — temporal smoothing across frames
* **SUMMARY** — (optional) post-aggregation or finalization stage

---

# 2. High-Level Flow Diagram

```
FRAME
 ↓
VEHICLE_DETECT
 ↓ (one per vehicle)
PLATE_DETECT
 ↓ (best plate per vehicle)
OCR
 ↓ (one result per plate)
PLATE_SMOOTH
 ↓ (after ≥2 samples per track_id)
SUMMARY
 ↓
Final plate written to Postgres
```

All intermediate outputs are stored in SQLite and fed through the **Dispatcher**.

---

# 3. Frame Entry → VEHICLE_DETECT

A `VideoReader` thread reads one frame at a time and:

1. Stores the frame in `frame_store`, generating a unique `payload_ref` such as:

   ```
   2025_1116_115002_000153F_01234
   ```

2. Creates a `VEHICLE_DETECT` task:

   ```python
   Task(
       category=VEHICLE_DETECT,
       payload=frame,
       priority=0,
       video_id=...,
       frame_idx=...,
       meta={
           "payload_ref": payload_ref,
           "dependencies": [payload_ref],
       }
   )
   ```

3. Pushes task into `CentralTaskQueue`.

---

# 4. VEHICLE_DETECT → PLATE_DETECT

A GPU worker pops a VEHICLE_DETECT task:

* Runs YOLO vehicle model
* Produces a list of detected vehicles (bounding boxes)

Dispatcher receives result and reloads the original frame from `frame_store` when downstream processors need pixels, then:

* For each vehicle detected, creates a **PLATE_DETECT** task with:

  * car bounding box
  * same dependencies

One vehicle → one PLATE_DETECT task.

---

# 5. PLATE_DETECT → OCR

A GPU worker pops a PLATE_DETECT task:

* Reloads the frame from `frame_store` using `payload_ref`
* Runs YOLO plate detection inside the car ROI
* Result is a list of potential plate boxes
* Dispatcher chooses the highest-confidence plate (if any)

Dispatcher creates an **OCR** task:

* Includes both car_bbox and plate_bbox
* Same dependency list

---

# 6. OCR → PLATE_SMOOTH

A GPU worker pops the OCR task:

* Reloads the frame from `frame_store` using `payload_ref`
* Extracts plate ROI
* Runs model to read text
* Produces:

  ```json
  { "text": "ABC123", "conf": 0.92 }
  ```

Dispatcher receives result and enqueues a **PLATE_SMOOTH** task.

---

# 7. PLATE_SMOOTH

A CPU worker pops the PLATE_SMOOTH task and:

* Appends (text, conf) pair into a global smoothing cache:

  ```python
  _global_plate_cache[(video_id, track_id)].append((text, conf))
  ```

* If fewer than 2 samples exist → returns `{ "final": None }`

* If 2+ samples exist → returns `{ "final": best_plate }`

Where `best_plate` is chosen by confidence-weighted voting, keyed by `(video_id, track_id)`.

Dispatcher then:

* If `final` is not None → enqueues a SUMMARY task
* Else → just marks result handled

---

# 8. SUMMARY → Postgres

A CPU worker pops SUMMARY:

* Performs any final aggregation
* Calls `writer.write_vehicle()` to insert a row into Postgres:

```
INSERT INTO vehicles (video_id, frame_idx, ts, final_plate, ...)
```

Dispatcher marks result handled.

---

# 9. Dependency-Based Frame Cleanup

Whenever dispatcher handles a result, it checks:

```
if no other tasks depend on this payload_ref:
    frame_store.delete_frame(payload_ref)
```

This reclaim storage for frames as soon as work is complete.

---

# 10. Worker-Side Flow

Each worker follows the same pattern:

1. Pick the busiest category relevant to worker type
2. Load model/resources on category switch
3. Pop task
4. Process it
5. Write result to SQLite
6. Update worker_status

Workers stop cleanly when `terminate.is_set()` becomes True.

---

# 11. Summary

This document describes the *exact* flow a frame takes through the system — from initial ingestion all the way to Postgres insertion. It’s the authoritative reference for how data moves through the pipeline.

Use this when debugging, extending the pipeline, or onboarding new contributors.
