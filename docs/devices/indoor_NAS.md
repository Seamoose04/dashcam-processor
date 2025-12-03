# Indoor NAS

The Indoor NAS is the **entry point for all raw dashcam footage** and the central storage hub for early-to-mid pipeline stages. It acts as the foundation upon which ingestion, preprocessing, and heavy processing depend.

Its primary role is to reliably receive videos, store them predictably, and serve them over the network to other devices in the pipeline.

---

# 1. Responsibilities

The Indoor NAS handles:

* Running `viofosync` to automatically download new dashcam footage
* Providing a stable location for raw video storage
* Hosting directory structures used by both Jetson and 4090
* Serving as the central file source for all upstream processing
* Holding certain intermediate artifacts (e.g., Jetson preprocessing output)
* Ensuring durable, persistent video storage until the pipeline completes

The Indoor NAS does **not** perform any video processing or task logic.

---

# 2. Directory Structure

The Indoor NAS stores footage and preprocessed artifacts using a consistent, timestamped folder structure:

```
/videos/
    raw/
        <trip_date>/
            front_xxxx.mp4
            rear_xxxx.mp4
    preproc/
        <video_id>/
            candidates.json
            thumbs/
                frame_001_thumb.jpg
                frame_002_thumb.jpg
    heavy_output/
        <video_id>/
            detections.json
            plate_crops/
```

This structure keeps all early pipeline data in a single predictable location.
Heavy outputs here are **intermediate**; finalized media moves to the Shed NAS and finalized metadata lives on the main server.

---

# 3. Ingestion via viofosync

The Indoor NAS runs the docker container:

```
RobXYZ/viofosync
```

Which is responsible for:

* Detecting when the dashcam becomes reachable
* Pulling new video files
* Storing them into `/videos/raw/<trip>/`
* Skipping previously downloaded files

After writing a new file, it triggers **task creation on the Main Server** (via a lightweight ingestion daemon).

---

# 4. Interaction With Devices

## 4.1 Jetson + Coral

* Reads raw video files directly from the NAS
* Writes small preprocessing outputs (JSON + thumbnails)
* Does NOT keep large files on NAS during its work

## 4.2 4090 Machine

* Streams full-resolution video directly from the NAS
* Writes detection metadata and best-crop outputs to NAS
* Never stores long-term intermediates outside of NAS

## 4.3 Main Server

* Monitors NAS for new files
* Creates ingestion tasks accordingly
* May store small task metadata alongside video folders

---

# 5. Storage Strategy

The Indoor NAS is optimized for:

* High read throughput (Jetson + 4090)
* Moderate write throughput (dashcam upload + preprocessing output)
* Reliable long-term raw video storage until processing is complete

After the 4090 machine finishes heavy processing:

* Raw full-resolution videos may be **de-res’d**
* Final archival media versions are moved to the Shed NAS
* Final metadata is forwarded to and persisted on the main server
* Raw videos may be pruned based on retention policies

---

# 6. Failure & Recovery Behavior

### If the Indoor NAS loses power:

* Dashcam upload pauses but resumes once online
* No tasks are corrupted because task state is managed by the Main Server
* Jetson and 4090 simply retry reads when NAS becomes reachable

### If a file transfer is interrupted:

* `viofosync` retries automatically
* Corrupted/partial files are ignored until fully transferred

### If the NAS runs low on space:

* The Main Server may schedule archival or deletion tasks

---

# 7. Summary

The Indoor NAS is the **data backbone** of the early pipeline. It:

* Receives raw footage reliably
* Serves as the shared file system for Jetson and 4090 processing
* Stores preprocessed outputs and heavy-processing metadata
* Ensures all devices have unified access to consistent paths
* Remains simple, durable, and predictable

It forms the hub through which all early-stage pipeline data flows, enabling the downstream devices to operate asynchronously and interruption-free.
