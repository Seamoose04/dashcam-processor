# Dashcam Pipeline Processors – Vehicle Tracking Design Doc

## Overview

Tracking determines **which detections across frames belong to the same physical vehicle**.

In the Dashcam Pipeline, tracking is essential for:

* Plate smoothing (requires consecutive OCR results for the *same* vehicle)
* Reducing duplicate output records
* Enabling consistent metadata across frames
* Ensuring final DB entries represent actual cars, not frame-level noise

Because workers run in parallel and frames are processed out of order, tracking **cannot** rely on YOLO’s built-in tracker, which only works sequentially.

Instead, tracking is a **separate processing stage** that assigns stable IDs *after* all vehicle detections are produced.

---

## Goals

1. **Stability** – same car keeps the same ID across frames.
2. **Parallelizable** – processing must work across multiple workers.
3. **Minimal CPU overhead** – tracking is far cheaper than detection/ocr.
4. **Stateless workers** – no single worker owns the track state.
5. **Robust to occlusion** – handle cars that temporarily disappear.
6. **Deterministic** – same input should produce same final IDs.

---

## Pipeline Placement

Tracking inserts **between VEHICLE_DETECT and PLATE_DETECT**.

### Original

```
VEHICLE_DETECT → PLATE_DETECT → OCR → PLATE_SMOOTH
```

### With Tracking

```
VEHICLE_DETECT → TRACK_ASSIGN → PLATE_DETECT → OCR → PLATE_SMOOTH
```

---

## TRACK_ASSIGN Responsibilities

1. Read detections for a frame (bbox + confidence).
2. Match them to existing active tracks:

   * via IoU
   * via centroid distance
   * via motion prediction (optional)
3. Assign track IDs to each vehicle.
4. Update the central TrackStore.
5. Output the detections with `track_id` included.

---

## How Tracking Works

Tracking is maintained inside a **global TrackStore** (multiprocessing-safe):

* keyed by `video_id`
* each video has a list of active tracks
* each track has:

  * `track_id`
  * last seen bbox
  * last frame index
  * number of misses
  * optional feature embedding (future extension)

### Matching

For each detected bbox in the current frame:

1. Compute IoU with all active track bboxes.
2. Compute centroid distance.
3. Select the best track if:

   * IoU > threshold, or
   * distance < threshold

If no match:

* Create a new track_id.

If track hasn't been seen for N frames:

* Mark as dead.

---

## Matching Algorithm (Pseudocode)

```
for each det in detections:
    best_track = None
    best_score = 0

    for track in active_tracks:
        iou = IoU(det.bbox, track.bbox)
        if iou > IOU_THRESHOLD:
            if iou > best_score:
                best_score = iou
                best_track = track

    if best_track:
        assign track_id from best_track
        update track bbox + frame index
    else:
        new_track = create new track
        assign new_track.track_id
```

---

## Multiprocessing Considerations

Tracking must NOT rely on any single worker.

Instead:

* TRACK_ASSIGN is a **CPU category**.
* All workers share a multiprocessing-safe TrackStore (Manager dict or SQLite table).
* Each TRACK_ASSIGN task updates the shared state atomically.

### Option A – Manager().dict() (simple)

Pros: fast, zero DB overhead.
Cons: large dictionaries might have overhead.

### Option B – SQLite table (robust)

Pros: survives crashes, fully persistent.
Cons: small overhead per read/write.

Recommended: **SQLite** because results matter long-term.

---

## Output

TRACK_ASSIGN outputs a list of:

```
{
  "bbox": [...],
  "track_id": <int>,
  "conf": <float>
}
```

This now replaces YOLO’s unreliable built-in `track_id`.

---

## Integration Changes

### In dispatcher

Replace:

```
VEHICLE_DETECT → PLATE_DETECT
```

With:

```
VEHICLE_DETECT → TRACK_ASSIGN → PLATE_DETECT
```

### In worker categories

CPU categories gain:

```
TaskCategory.TRACK_ASSIGN
```

### In pipeline

Plate smoothing now uses:

```
(video_id, track_id)
```

Instead of:

```
(video_id, car_bbox)
```

---

## Why Not Use YOLO Track Directly?

* Requires strictly sequential frames
* Not compatible with many-GPU parallel processing
* Produces different IDs based on processing throughput
* Cannot survive reordering of frames

Our tracking layer is **deterministic**, **parallel-safe**, and **resilient**.

---

## Future Extensions

### 1. Feature-based Tracking

Use a tiny ReID embedding model.

### 2. Motion Prediction

Use a Kalman filter per track.

### 3. 3D Tracking

If a depth camera exists in future videos.

### 4. Plate-aware feedback

If OCR stays consistent, use it to reinforce identity.

---

## Summary

Tracking is crucial for stable, reliable multi-frame processing and final database output.
It provides consistent `track_id`s across frames, enabling:

* plate smoothing
* duplicate suppression
* correct vehicle grouping
* consistent metadata

Tracking operates as a **CPU-only step** and bridges the gap between raw YOLO detections and higher-level understanding.
