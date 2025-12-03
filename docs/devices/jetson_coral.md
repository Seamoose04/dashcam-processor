# Jetson + Coral

The Jetson Nano (with the USB Coral TPU attached) serves as the **first compute stage** of the pipeline. Its role is to reduce workload on the 4090 machine, quickly filter video content, and prepare structured data for heavy GPU processing.

This stage emphasizes **speed, efficiency, and early data reduction**, while keeping all work fully restartable through the task system.

---

# 1. Responsibilities

The Jetson + Coral subsystem performs:

* Pulling preprocessing tasks from the main server
* Reading raw video files directly from the Indoor NAS
* Extracting low-resolution frames or thumbnails
* Motion filtering to discard empty/useless frames
* Coral-based plate region proposals
* Basic heuristics (lighting, blur, distance estimation)
* Producing small preprocessed artifacts for downstream use
* Storing temporary files locally during execution
* Publishing downstream heavy-processing tasks upon completion

This stage ensures that the 4090 machine only works on frames that truly matter.

---

# 2. How Tasks Are Pulled

Jetson pulls tasks of type:

```
PREPROCESS_VIDEO
```

These tasks contain:

* Path to raw video on Indoor NAS
* Parameters for extraction rate, resolution, filtering thresholds

Jetson is never pushed work by other devices or by the server—it *only pulls*.

---

# 3. Preprocessing Steps

The following lightweight or Coral-accelerated steps occur on the Jetson.

## 3.1 Low-Resolution Frame Extraction

* Jetson extracts frames at full framerate but low resolution
* Reduces decoding cost
* Frames are stored locally in Jetson’s scratch directory
* Used as input for motion + plate proposal models

## 3.2 Motion Filtering

* Simple frame delta or optical flow (Jetson-side)
* Discards any consecutive frames that:

  * contain no movement
  * contain no meaningful structure
  * are too dark or too blurry

This drastically reduces workload downstream.

## 3.3 Coral Plate Region Proposal

* A small, efficient MobileNet/SSD model on the Coral TPU
* Generates coarse bounding boxes for possible license plates
* Very cheap to run per-frame

Outputs:

* A JSON list of candidate plate regions per frame
* Optional thumbnails of the cropped regions

## 3.4 Additional Metadata Heuristics

* Rough lighting level
* Blur/clarity score
* Frame confidence composite
* Frame rejection reasons (for debugging)

### Key Note

All of the above outputs are *small*, allowing fast transfer to the 4090 machine.

---

# 4. Storage Behavior

During a preprocessing task:

* All temporary data is written **locally** on the Jetson
* No large files are kept
* Local files exist only as scratch work

After a successful completion:

* Important preprocessed artifacts (JSON + thumbnails) are written to Indoor NAS or left in a predictable location for the 4090
* Jetson deletes all other temporary data

On interruption:

* All local scratch must be deleted during reboot
* Jetson retries the whole task from scratch by pulling it again

---

# 5. Remote Task Creation

Once the Jetson completes its preprocessing task:

* It publishes a **remote heavy-processing task** for the 4090 machine
* It then marks the current preprocessing task as `complete`

This guarantees the heavy GPU stage only begins after clean preprocessing.

---

# 6. Interaction With the Indoor NAS

Jetson reads:

* Raw video files directly over Ethernet
* Metadata sidecar files if present

Jetson writes:

* Preprocessed artifacts (small JSON + thumbnails)
* Only the minimum needed for the 4090

The NAS remains the hub for all storage.

---

# 7. Interaction With the Main Server

Jetson communicates only by:

* Pulling `PREPROCESS_VIDEO` tasks
* Marking tasks `complete`
* Publishing remote heavy-processing tasks

Jetson never:

* Pushes tasks directly to other devices
* Stores its own tasks in the server DB
* Accepts tasks from other sources

This keeps its role strictly bounded.

---

# 8. Failure & Recovery Behavior

Because all Jetson work is deterministic:

### If Jetson loses power mid-task:

* All local scratch is discarded at boot
* The task remains `pending` on the server
* Jetson re-pulls the same task
* Recomputes everything identically
* Eventually completes and publishes downstream tasks

### If the Indoor NAS or network is unavailable:

* Task will fail to progress but not be corrupted
* Retry behavior is implicit

### If Coral TPU disconnects:

* Preprocessing task will fail
* Jetson will retry on next pull

This ensures robustness even with unreliable embedded hardware.

---

# 9. Summary

The Jetson + Coral subsystem serves as the pipeline's **early filter and lightweight preprocessor**. It:

* Reduces video complexity
* Identifies promising regions
* Produces compact, high-value metadata
* Ensures the 4090 receives only meaningful work
* Performs all operations in a fully restartable, interruption-safe manner

It is the perfect first compute stage in this distributed pipeline.
