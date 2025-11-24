# **Processor Design Guide**

### *How to implement a new GPU or CPU processor in the dashcam pipeline*

---

This document explains the **architecture**, **required structure**, **function signatures**, and **best-practices** for implementing a new processing stage in the pipeline.

Processors are the *core compute units* in the system — each performing one transformation on incoming tasks (YOLO detect, OCR, smoothing, summarizing, …).

The system currently supports:

* **GPU processors** (YOLO models, OCR models, etc.)
* **CPU processors** (plate smoothing, summary aggregation, etc.)

This guide fully defines how a processor must be structured so it can plug into the Worker → Dispatcher → Storage architecture without any modifications.

---

# 1. **Processor File Structure**

Every processor module must provide exactly two functions:

### **1. `load_<name>() → resource`**

Runs **once per worker**, loads heavy resources, models, or sets up CPU/GPU state.

### **2. `process_<name>(task, resource) → result_dict`**

Runs **once per task**, using the provided resource to transform the task into a result.

Minimal example:

```python
def load_my_processor():
    return HeavyModel("weights.bin")

def process_my_processor(task, model):
    output = model.infer(task.payload)
    return {"score": float(output)}
```

Both functions must be defined in the processor module and referenced by your **gpu_processors** or **cpu_processors** mapping.

---

# 2. **A Processor’s Inputs and Outputs**

Each processor receives:

```python
process(task: Task, resource: Any) -> dict
```

### `task` includes:

* `task.payload` — direct payload (like a frame or ROI image).
* `task.meta` — anything upstream processors added to the task.
* `task.video_id`
* `task.frame_idx`
* `task.track_id` (if assigned)
* `task.category`

### The return value **must be a dict**.

Example:

```python
return {
    "bbox": [...],
    "conf": 0.92,
    "track_id": 3
}
```

If a processor produces *multiple* outputs, return a list of dicts.

If it has *no result*, return `{}` or an empty list.

The dict is saved to SQLite and dispatched to the next stage.

---

# 3. **GPU Processor Requirements**

GPU processors run inside `GPUWorkerProcess` and must follow these rules:

### ✔ DO:

* Accept a NumPy `frame` or ROI directly (`task.payload`)
* Return a list of detection dicts OR a single dict
* Load heavy YOLO/OCR weights in `load_<name>()`
* Suppress model print output with `suppress_stdout()`

### ✘ DO NOT:

* Load models inside `process_*`
* Use global state
* Modify task ids or queue ordering
* Return non-JSON-serializable values
* Access shared CPU SQLite connections

Example GPU processor (your YOLO vehicle one):

```python
def process_vehicle(task: Task, model: YOLO):
    frame = task.payload
    with suppress_stdout():
        results = model.track(frame, persist=True)[0]

    detections = []
    for box in results.boxes:
        ...
        detections.append({
            "bbox": [...],
            "track_id": track_id,
            "conf": conf,
        })
    return detections
```

---

# 4. **CPU Processor Requirements**

CPU processors run inside `CPUWorkerProcess` and:

### ✔ DO:

* Use `task.meta` instead of large arrays
* Perform lightweight CPU work
* Merge, smooth, reduce, validate, or filter results
* Use stable identifiers (`task.track_id`)

### ✘ DO NOT:

* Load GPU models here
* Modify global or shared data in a non-safe way
* Rely on order (tasks may arrive async)

Example CPU processor (your plate_smooth):

```python
def process_plate_smooth(task, resource):
    vid = task.video_id
    tid = task.track_id

    text = task.meta.get("text")
    conf = task.meta.get("conf")

    key = (vid, tid)
    if text:
        _global_plate_cache[key].append((text, conf))

    guesses = _global_plate_cache[key]
    if len(guesses) >= 2:
        final = _merge_strings(guesses)
        return {"final": final, "conf": max(c for _, c in guesses)}

    return {"final": None}
```

---

# 5. **Resource Loaders (`load_*`)**

Called once per worker when the worker switches into that category.

### Loaders must:

* Load models
* Initialize lookup tables
* Open large files
* Return a ready-to-use resource

Example:

```python
def load_ocr():
    return TrOCR("weights/ocr.onnx")
```

If no resource is needed:

```python
def load_plate_smoother():
    return None
```

---

# 6. **Processor Output → Dispatcher → Next Stage**

The Dispatcher receives the processor output and calls the appropriate handler:

Example handler usage:

```python
handle_vehicle_detect_result(vehicle_result)
```

Handlers build **new Tasks** using the result:

* VEHICLE_DETECT → PLATE_DETECT
* PLATE_DETECT → OCR
* OCR → PLATE_SMOOTH
* PLATE_SMOOTH → summary/write path

Handlers expect payload/meta to include the references needed to reload frames (`payload_ref`, bboxes). PLATE_DETECT and OCR processors read pixels back from `frame_store` using those references; their task.payload only carries bbox metadata, not the actual ROI.

Your processor output must therefore include **all information needed for the handler**.

For example OCR must produce:

```python
return {
    "text": "EYU",
    "conf": 0.87,
    "car_bbox": [...],
    "plate_bbox": [...]
}
```

---

# 7. **Adding a New Processor**

Steps:

### 1. Create a new Python file

`pipeline/processors/my_stage.py`

### 2. Add two functions:

```python
def load_my_stage():
    ...

def process_my_stage(task, resource):
    ...
```

### 3. Register it in `pipeline/categories.py`

```python
gpu_categories.append(TaskCategory.MY_STAGE)
gpu_processors[TaskCategory.MY_STAGE] = process_my_stage
gpu_resource_loaders[TaskCategory.MY_STAGE] = load_my_stage
```

(or CPU category)

### 4. Create a handler in `dispatch_handlers.py`

```python
def handle_my_stage(task_id, result, queue, db):
    new_task = Task(...)
    queue.push(...)
    db.save_task(...)
```

### 5. Make sure downstream processors handle `"meta"` fields correctly.

---

# 8. **Best Practices**

### ❗Do not store large arrays in SQLite meta

Use `frame_store` + `payload_ref`.

### ❗Never do `cv2.imread()` inside a CPU processor

Heavy I/O belongs to GPU stage or video reader.

### ❗Never call another processor from inside a processor

Use the dispatcher.

### ❗Always return a dict or list-of-dicts

Never return raw objects (NumPy arrays, YOLO objects).

### ❗If your processor is merging outputs across frames

Use `(video_id, track_id)` as the cache key.

For example, plate smoothing emits `{"final": None}` until it has at least two samples for a `(video_id, track_id)` pair, then returns the best consensus plate and confidence.

---

# 9. **Example Complete Processor Template**

```python
# processors/my_detector.py
from pipeline.task import Task
from pipeline.silence import suppress_stdout

def load_my_detector():
    from some_model_lib import Model
    with suppress_stdout():
        return Model("weights.bin")

def process_my_detector(task: Task, model):
    image = task.payload

    with suppress_stdout():
        out = model.predict(image)

    return {
        "value": float(out.score),
        "bbox": list(map(float, out.bbox)),
    }
```

---

# 10. **FAQ**

### Q: Can a processor create more than one downstream task?

Yes. Return a list of dicts; the handler will fan them out.

### Q: Can processors share state?

Only CPU processors *can*, using internal module globals — but must be idempotent and keyed by `(video_id, track_id)`.

### Q: Can GPU processors store global state?

No — multiple GPU workers run in parallel.

---
