# Shed NAS

The Shed NAS is the **final archival destination** for all processed dashcam videos and plate crops. It holds the de-res’d, long-term versions of each video, along with high-resolution plate crops used by the WebUI. Once data reaches the Shed NAS, it is considered finalized and ready for long-term storage and viewing.

This device acts as the **cold storage layer** and the **media backend** for the entire system.

---

# 1. Responsibilities

The Shed NAS is responsible for:

* Receiving archival tasks from the main server
* Storing permanently de-res’d versions of processed videos
* Storing full-resolution plate crops for verification
* Serving finalized media directly to the WebUI
* Maintaining long-term storage of finalized video and crop assets only

The Shed NAS does *not* perform any compute or preprocessing.

---

# 2. Directory Structure

The Shed NAS organizes final output into predictable archival folders:

```
/archive/
    <video_id>/
        video_lowres.mp4
        plates/
            <plate_id>_best_crop.jpg
```

### Contents Explained

* `video_lowres.mp4` — the low-resolution full video, kept for context
* `plates/` — high-res plate crops (kept full resolution for verification)

Only finalized media assets live here; metadata remains on the main server.

---

# 3. Interaction With Other Devices

## 3.1 Main Server

* Publishes archival tasks when heavy processing is complete
* Coordinates retention and deletion policies

## 3.2 4090 Machine

* Sends:

  * De-res’d video (if 4090 performs transcoding)
  * Full-resolution plate crops
* Only writes to the Shed NAS *after* its task is fully complete

## 3.3 Jetson + Coral

* Does not interact directly with the Shed NAS

---

# 4. Archival Workflow

When the Shed NAS processes an archival task:

1. It receives a finalized bundle from the server or 4090
2. It creates an archival folder: `/archive/<video_id>/`
3. It stores:

   * Low-res video
   * High-res plate crops
4. It confirms successful write
5. It marks the archival task as `complete`
6. The main server may then schedule deletion of older raw/intermediate data

This marks the **end of the pipeline** for that video.

---

# 5. Media Serving for WebUI

The Shed NAS is the backend source for all WebUI media displays:

* De-res’d archival video
* High-resolution plate crops

WebUI reads data directly via:

* SMB
* HTTP file server
* NFS
* Or through a lightweight NAS-mounted backend API

Metadata is read from the main server database; the Shed NAS does not store or cache metadata.

---

# 6. Retention & Cleanup Responsibilities

The Shed NAS participates heavily in long-term storage management:

* Stores only final outputs (no intermediates)
* Raw videos are *not* kept here
* Jetson scratch and 4090 scratch are never stored on the Shed NAS
* Low-resolution videos replace original full-res versions
* Plate crops remain full-res

Optional configurable policies:

* Delete low-res videos after X months
* Keep high-res crops indefinitely
* Archive video summaries to cold storage
* Auto-clean missing/corrupted entries

---

# 7. Failure & Recovery Behavior

### If Shed NAS loses power:

* All intermediate work remains safe (stored on server, 4090, or Indoor NAS)
* Archival tasks remain `pending`
* When NAS returns, archival tasks simply re-run

### If a transfer is interrupted:

* Device performing the transfer fails safely
* Task is not marked complete
* On retry, the entire archival step is recomputed

This keeps archival tasks fully deterministic and safe.

---

# 8. Summary

The Shed NAS is the **final resting place** for all pipeline media outputs. It stores the compact, curated video data required for long-term retention and WebUI display, while metadata remains on the main server.

It guarantees that once a video reaches the Shed NAS, it is fully processed, context-rich, and ready for browsing—allowing the pipeline to safely delete all earlier-stage data and free up storage throughout the system.
