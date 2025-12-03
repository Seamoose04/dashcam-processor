# Dashcam

The dashcam is the origin point of all data in the pipeline. Its sole responsibility is to reliably record raw driving footage and make those recordings available for ingestion once the vehicle returns home.

---

# 1. Responsibilities

* Record high‑resolution video files during driving
* Store files on its internal SD card
* Provide access to those files over Wi‑Fi or via removable storage
* Preserve accurate timestamps in file metadata
* Optionally include GPS data (if supported by the model)

The dashcam performs **no processing**, **no uploading**, and **no filtering**. It simply acts as the initial data generator.

---

# 2. File Characteristics

Typical output includes:

* Video files in MP4 format
* Filenames containing timestamps
* Continuous loops split into segments (1–5 minutes each)
* Metadata that may include:

  * Recording start time
  * Resolution and frame rate
  * (Optional) Embedded GPS coordinates

These raw files are required for the highest‑accuracy plate and vehicle detection.

---

# 3. How the Dashcam Integrates into the Pipeline

When the car arrives home:

* The dashcam connects (or is reachable) via Wi‑Fi
* The Indoor NAS runs `viofosync` or an equivalent sync tool
* `viofosync` pulls new videos from the dashcam automatically
* Each new file is saved into:

  ```
  /videos/raw/<trip>/
  ```

The dashcam itself remains passive during this transfer.

---

# 4. Reliability Considerations

* If the dashcam powers down mid‑sync, only complete files are used
* The sync tool detects duplicates and only pulls new files
* The pipeline tolerates missing or corrupted files gracefully
* No processing occurs directly on the dashcam, avoiding load or instability

---

# 5. Summary

The dashcam is a simple, dedicated recording device. It captures the high‑resolution footage needed for accurate plate detection, hands off its files to the Indoor NAS via automated sync, and plays no further role in the processing pipeline.
