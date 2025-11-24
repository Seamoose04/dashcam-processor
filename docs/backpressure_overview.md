# Backpressure in the Dashcam Pipeline

Backpressure is a **core stability mechanism** in the Dashcam Processing Pipeline. It ensures that video readers, GPU workers, CPU workers, and the dispatcher remain in sync and that **no part of the system produces work faster than the rest can consume it**.

Without backpressure, the system would rapidly exceed available RAM, overwhelm the GPU, and stall due to thousands of queued tasks.

This document explains how backpressure works, why we use it, and how it dynamically keeps the pipeline healthy at high throughput.

---

## 1. What Backpressure Solves

### **Problem: Readers are too fast.**

Video readers can decode frames at **hundreds of FPS**, while object detection (YOLO) often runs at **5–40 FPS** depending on model and hardware.

If readers run unchecked:

* GPU queue explodes
* CPU queue piles up
* SQLite DB grows uncontrollably
* RAM fills with pending frames
* Worker processes begin thrashing

### **Backpressure prevents this.**

The pipeline slows down *production* (i.e., readers) when *consumption* (i.e., workers) falls behind.

It is a feedback loop:

* Too many queued GPU jobs → pause readers
* Too many queued CPU jobs → pause readers
* Queues shrink → resume readers

The system automatically stabilizes.

---

## 2. Where Backpressure Lives: The VideoReader

Backpressure is currently evaluated *entirely within the VideoReader*. This is ideal because it prevents unnecessary frames from hitting the rest of the pipeline.

```python
if self.gpu_overloaded() or self.cpu_overloaded():
    time.sleep(self.sleep_interval)
    continue
```

This means **we stop producing frames** whenever the pipeline is overloaded.

Nothing upstream needs to know.

---

## 3. Backpressure Rules

### **GPU Backpressure**

Triggered when total queued tasks in these categories exceed `MAX_GPU_BACKLOG`:

* VEHICLE_DETECT
* PLATE_DETECT
* OCR

These are the expensive YOLO/AI tasks. When they pile up, readers must slow down.

### **CPU Backpressure**

Triggered when queued tasks exceed `MAX_CPU_BACKLOG`:

* PLATE_SMOOTH
* SUMMARY

These are cheap, but still can backlog when GPU output surges.

Readers pause until queues fall below the threshold again.

---

## 4. Environment Variables

These control how aggressively backpressure triggers:

```
MAX_GPU_BACKLOG=100
MAX_CPU_BACKLOG=100
```

### **Interpretation:**

* If **GPU queue > 100** items, readers pause.
* If **CPU queue > 100** items, readers pause.

Tune these based on hardware:

* Big GPU (4090 / A100): raise GPU backlog
* Weak GPU (Jetson): lower it
* Lots of CPU cores: raise CPU backlog

---

## 5. Why Queues Are the Best Signal

The alternative backpressure signals include:

* GPU utilization
* worker idle times
* model inference queue lengths
* frame-store memory pressure

But queue depth is *proven* to work best because it directly measures:

* "How behind are we?"
* "How long until a new frame gets processed?"
* "Are we at risk of falling over?"

Queue depth is stable, easy to compute, and represents real work.

---

## 6. Backpressure Flow Diagram

```
[VideoReader Threads]
        |
        v
   [Check Backlog]
    /             \
(GPU/CPU>limit)   (OK)
    |                \
[Pause Readers]     [Enqueue Frame]
    |                   |
    v                   v
[sleep N ms]     [Push VEHICLE_DETECT]
                        |
                        v
                [GPU/CPU Workers Consume]
                        |
                        v
                 [Backlog Shrinks]
                        |
                        +----> (feedback to Check Backlog)
```

This is a classic feedback loop.

---

## 7. Behavior During Overload

When GPU queue hits the limit:

* Readers go into a **sleep loop** (0.02s per iteration)
* Workers continue processing
* Backlog shrinks
* Readers wake up automatically

When CPU queue hits the limit:

* Same behavior

Backpressure therefore acts as a natural stabilizer.

---

## 8. Why Backpressure Improves Tracking Quality

Tracking quality is best when frames are processed **in-order**.

Without backpressure:

* Frames pile up
* GPU may process frame 0, then frame 200, then frame 50
* Track IDs become meaningless
* Plate smoothing never forms a stable consensus

Backpressure preserves ordering by regulating input rate.

---

## 9. Future Extensions

We may extend backpressure with:

* Per-category dynamic thresholds
* Adaptive sleep based on backlog slope
* GPU utilization-based slowdown
* Memory-based throttling
* Prioritizing keyframes in overload

These can be added without breaking the current design.

---

## 10. Summary

Backpressure is essential for:

* Preventing memory explosions
* Keeping tracking stable
* Ensuring workers don’t starve or thrash
* Maintaining in-order processing
* Allowing *N* video readers to safely run in parallel

The current implementation is simple, stable, and scalable.

Backpressure keeps the entire Dashcam pipeline **healthy, adaptive, and real‑time capable**.
