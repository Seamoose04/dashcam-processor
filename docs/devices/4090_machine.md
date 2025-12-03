# 4090 Machine

The Windows PC with the RTX 4090 GPU is the **heavy-processing engine** of the entire pipeline. It performs all computationally expensive tasks, including full-resolution object detection, OCR, and GPS alignment, while also managing final per-video decisions such as plate selection and metadata consolidation.

The 4090 behaves as an autonomous worker device that pulls tasks, performs deterministic local work, and publishes downstream tasks only upon successful completion.

---

# 1. Responsibilities

The 4090 machine is responsible for:

* Pulling heavy-processing tasks from the main server
* Reading preprocessed artifacts from Jetson / Indoor NAS
* Loading full-resolution frames or video segments only when needed
* Running full-resolution YOLO plate + vehicle detection
* Running GPU-accelerated OCR on extracted plate crops
* Performing GPS alignment & frame timestamp matching
* Selecting best crops and best frames
* Generating final per-vehicle and per-plate metadata
* Storing temporary data locally during execution
* Publishing remote archival/finalization tasks upon completion

The 4090 is optimized for **occasional bursts of heavy compute**, e.g. running overnight.

---

# 2. How Tasks Are Pulled

The 4090 pulls tasks of type:

```
HEAVY_PROCESS_VIDEO
```

Tasks specify:

* Video ID
* Paths to raw video on the Indoor NAS
* Paths to Jetson preprocessing outputs

Upon pulling, the 4090 becomes the sole executor of that heavy-processing task.

---

# 3. Heavy Processing Steps

All the computationally expensive work happens here.

## 3.1 YOLO Full-Resolution Detection

* Runs high-accuracy YOLO model on selected frames
* Uses Jetson’s region proposals to limit search space
* Outputs bounding boxes for:

  * License plates
  * Vehicles
  * Optional: headlights, brake lights, pedestrians, etc.

## 3.2 Plate Crop Extraction

* Extracts high-resolution plate crops from full frames
* Stores crops in temporary local SSD folder
* Keeps only the minimal set needed for OCR and final archival

## 3.3 GPU OCR

* Uses GPU-accelerated OCR (e.g., EasyOCR GPU mode)
* Runs on each plate crop
* Performs multi-candidate aggregation
* Combines multiple-frame results for plate stabilization (confidence voting)

## 3.4 GPS Timestamp Alignment

* Loads GPS log (if present) or sidecar data
* Performs timestamp-based interpolation to map frame index → GPS coordinate
* Produces per-frame GPS metadata:

  * lat/lon
  * speed
  * bearing
  * accuracy

## 3.5 Best Crop & Best Frame Selection

* Chooses the best-quality crop for each detected plate
* Selects representative frames for the WebUI

## 3.6 Metadata Consolidation

* Creates final structured data for each plate and vehicle:

  * full timeline across frames
  * confidence scores
  * movement vectors
  * GPS positions
  * detection summaries

All outputs are small and highly structured.

---

# 4. Storage Behavior

During task execution:

* All heavy intermediates (frames, crops, temp metadata) are kept **locally** on 4090’s fast SSD
* Nothing is written to NAS until the task fully completes
* Raw video is streamed directly from the Indoor NAS

After completion:

* Media outputs (de-res video, plate crops) are pushed to the Shed NAS via the archival task flow
* Final metadata is sent to the main server
* Local temp files are deleted

On interruption:

* Local scratch is cleared automatically at startup
* The task remains `pending` on the server
* 4090 simply pulls the same task again and recomputes

This ensures fully deterministic recovery.

---

# 5. Remote Task Creation

Once heavy processing is complete:

* The 4090 publishes a **remote archival task** (usually handled by the server or Shed NAS)
* Then marks the heavy-processing task as `complete`

Remote task creation always happens **after** completion, preventing duplicates.

---

# 6. Interaction With Other Devices

## 6.1 Indoor NAS

* Reads full-resolution video via LAN
* Writes heavy-processing output (e.g. detection metadata) only as intermediate artifacts

## 6.2 Jetson

* Reads Jetson preprocessing artifacts (JSON + thumbnails)
* Jetson never pushes tasks to the 4090; the 4090 always pulls

## 6.3 Main Server

* Pulls tasks from server DB
* Marks tasks complete
* Publishes downstream tasks when finished
* Receives final metadata for long-term storage and WebUI indexing

## 6.4 Shed NAS

* Sends archival media (de-res video, crops) after the remote archival task is created

---

# 7. Scheduling & Usage Pattern

The 4090 typically:

* Remains idle during the day (or available for normal use)
* Runs heavy-processing tasks **overnight**
* Pulls tasks only when the system is not being actively used (optional throttling)

Future improvements may include:

* Power-based scheduling
* CPU/GPU-usage thresholds
* Automatic pausing if the 4090 becomes busy

---

# 8. Failure & Recovery Behavior

Because all work is deterministic:

### If the 4090 crashes mid-task:

* Local scratch is discarded at reboot
* Task remains `pending` on server
* 4090 pulls the task again
* Fully recomputes

### If network storage is unavailable:

* 4090 simply waits and retries

### If user interrupts to play games:

* Local work stops instantly
* Device resumes processing later when allowed

This level of fault-tolerance allows the 4090 to work opportunistically.

---

# 9. Summary

The 4090 machine is the **core computational powerhouse** of the pipeline. It performs full-resolution detection, OCR, GPS alignment, and metadata consolidation, all while minimizing its footprint through temporary local storage and strict task-system semantics.

Its role ensures maximal accuracy for plate readings and vehicle tracking, while remaining perfectly resilient to interruptions and power cycles.
