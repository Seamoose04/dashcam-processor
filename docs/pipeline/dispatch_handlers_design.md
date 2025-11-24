# Dashcam Pipeline – Dispatch Handlers Design Doc

This document describes the design, responsibilities, patterns, and integration rules
for the **Dispatcher Handlers** — the glue code that transforms processor output into
new tasks for the pipeline.

Handlers are the ONLY place where:
- processor outputs are interpreted
- new Tasks are created
- Tasks are pushed into the queue
- task metadata is validated or enriched
- final results are forwarded to the Writer / Postgres system

Think of handlers as the **flowchart logic** of the entire pipeline.

---

# 1. Purpose of the Dispatcher

The Dispatcher:

1. Monitors SQLite for completed tasks  
2. Loads their results  
3. Determines the correct handler  
4. Calls handler(result)  
5. Records new downstream tasks  
6. Marks the old task as “dispatched”

Handlers encapsulate the logic for #4 and #5.

---

# 2. Handler Function Requirements

Every handler has the same signature:

```python
def handle_<stage>_result(
    result_id: int,
    task_id: int,
    category: TaskCategory,
    task: Task,
    result_obj: dict | list,
    db: SQLiteStorage,
    queue: CentralTaskQueue,
):
    ...
````

All handlers MUST:

### ✓ Accept:

* `task`: the original Task
* `result_obj`: the processor output dict (or list)
* `queue`: CentralTaskQueue instance
* `db`: SQLiteStorage instance

### ✓ Return:

Nothing (handlers push new tasks directly)

### ✓ MUST NOT:

* return new tasks
* call processors directly
* block or sleep
* perform heavy CPU/GPU work
* modify global system state

---

# 3. Handler Lifecycle

A handler lives inside this loop (Dispatcher):

```
for each completed task:
    result = db.fetch_result(task_id)
    handler = handlers[task.category]
    handler(result_id, task_id, task.category, task, result, db, queue)
    db.mark_dispatched(task_id)
```

This ensures:

* each processor output is handled exactly once
* handlers cannot stall the pipeline
* ordering does not matter (workers run async)

---

# 4. Handler Responsibilities

### 4.1. Read processor output

Handler sees raw outputs, e.g.:

```python
{"bbox": [...], "track_id": 3, "conf": 0.87}
```

### 4.2. Validate results

If invalid → drop.

### 4.3. Transform output into downstream tasks

Each detection, OCR result, or smoothed plate becomes a new Task.

### 4.4. Populate Task fields

Required Task fields:

```python
category: TaskCategory
payload: small direct payload (frame/ROI) or None
video_id
frame_idx
track_id
meta: dict
```

### 4.5. Save Task to SQLite

```
task_id = db.save_task(task)
```

### 4.6. Push Task into CentralTaskQueue

```
queue.push(task_id, task)
```

---

# 5. Concrete Handler Examples

Below are the canonical handlers from your system.

## 5.1. VEHICLE_DETECT → PLATE_DETECT

```python
def handle_vehicle_detect_result(task, result, queue, db):
    # result is a list of vehicle detections
    for det in result:
        bbox = det["bbox"]
        track_id = det.get("track_id")

        new_task = Task(
            category=TaskCategory.PLATE_DETECT,
            payload={"car_bbox": bbox},  # bbox metadata only; frame is reloaded via payload_ref
            video_id=task.video_id,
            frame_idx=task.frame_idx,
            track_id=track_id,
            meta={
                "payload_ref": task.meta.get("payload_ref"),
                "car_bbox": bbox,
                "dependencies": task.meta.get("dependencies", []),
            }
        )

        tid = db.save_task(new_task)
        queue.push(tid, new_task)
```

### NOTE:

* Track ID is propagated immediately.
* Vehicle bbox goes into `meta`.

---

## 5.2. PLATE_DETECT → OCR

```python
def handle_plate_detect_result(task, result, queue, db):
    # result is a list of plate ROIs with bboxes
    for det in result:
        plate_bbox = det["bbox"]

        new_task = Task(
            category=TaskCategory.OCR,
            payload={
                "plate_bbox": plate_bbox,
                "car_bbox": task.meta["car_bbox"],
            },
            video_id=task.video_id,
            frame_idx=task.frame_idx,
            track_id=task.track_id,
            meta={
                "payload_ref": task.meta.get("payload_ref"),
                "car_bbox": task.meta["car_bbox"],
                "plate_bbox": plate_bbox,
                "dependencies": task.meta.get("dependencies", []),
            }
        )

        tid = db.save_task(new_task)
        queue.push(tid, new_task)
```

### NOTE:

* Payload stays as bbox metadata; OCR reloads the plate ROI from `frame_store` using `payload_ref`
* Car bbox is inherited
* Plate bbox is added

---

## 5.3. OCR → PLATE_SMOOTH

```python
def handle_ocr_result(task, result, queue, db):
    text = result.get("text")
    conf = result.get("conf")

    new_task = Task(
        category=TaskCategory.PLATE_SMOOTH,
        payload=None,
        video_id=task.video_id,
        frame_idx=task.frame_idx,
        track_id=task.track_id,
        meta={
            "text": text,
            "conf": conf,
            "car_bbox": task.meta["car_bbox"],
            "plate_bbox": task.meta["plate_bbox"]
        }
    )

    tid = db.save_task(new_task)
    queue.push(tid, new_task)
```

### NOTE:

* Smoothing gets ONLY metadata (text/conf/bboxes)
* Payload is omitted to reduce CPU load

---

## 5.4. PLATE_SMOOTH → SUMMARY

```python
def handle_plate_smooth_result(task, result, queue, db):
    final = result.get("final")
    conf = result.get("conf")

    if final is None:
        return  # not enough samples yet

    new_task = Task(
        category=TaskCategory.SUMMARY,
        payload=None,
        video_id=task.video_id,
        frame_idx=task.frame_idx,
        track_id=task.track_id,
        meta={
            "final_plate": final,
            "conf": conf,
            "car_bbox": task.meta["car_bbox"],
            "plate_bbox": task.meta["plate_bbox"]
        }
    )

    tid = db.save_task(new_task)
    queue.push(tid, new_task)
```

### NOTE:

* PLATE_SMOOTH may produce multiple "final" events eventually
* We choose to output only once per stable final plate per track_id

---

## 5.5. SUMMARY → POSTGRES (final output)

Inside the Summary processor OR Writer:

```python
writer.write_vehicle(
    video_id=task.video_id,
    frame_idx=task.frame_idx,
    final_plate=final_plate,
    conf=conf,
    car_bbox=car_bbox,
    plate_bbox=plate_bbox,
)
```

---

# 6. Adding a New Handler

To add a new processor stage, you must:

### 1. Define a handler function

```python
def handle_newstage_result(task, result, queue, db):
    ...
```

### 2. Add it to the handler map in main.py or dispatcher:

```python
handlers = {
    TaskCategory.NEWSTAGE: handle_newstage_result,
    ...
}
```

### 3. Ensure the upstream processor returns the right structure

### 4. Ensure the downstream processor understands the `meta` fields you set

---

# 7. Handler Design Best Practices

### ✔ Use `task.track_id` for everything involving sequence or smoothing

This avoids YOLO track instability issues.

### ✔ Minimize payload size

Only pass large images when absolutely needed.

### ✔ Validate input

Bad OCR? Bad bbox? Skip instead of breaking the pipeline.

### ✔ Never block

Handlers must run instantly.

### ✔ Keep metadata consistent

If a stage expects `"car_bbox"`, always include it upstream.

### ✔ Keep handlers pure

They should behave like pure transform functions.

---

# 8. Summary

Each handler represents ONE arrow in the processing DAG:

```
VEHICLE_DETECT  →  PLATE_DETECT  →  OCR  →  PLATE_SMOOTH  →  SUMMARY → POSTGRES
```

Handlers are the lightweight glue that
keeps the system modular, testable, debuggable, and scalable.

When implementing a new processor stage,
**always start by designing its handler** —
this determines what shape the processor must output.

---
