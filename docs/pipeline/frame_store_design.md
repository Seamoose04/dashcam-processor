# Frame Store — Design & Architecture

This document explains the design of the disk-backed `frame_store` system. It is responsible for efficiently storing video frames during processing and freeing them as soon as downstream tasks no longer need them.

The frame store is one of the most important parts of the pipeline because it:

* Keeps RAM usage low
* Provides persistent access for GPU/CPU workers
* Ensures frames only exist as long as required by tasks
* Works safely across many threads and processes

---

# 1. Purpose

The `frame_store` component exists because:

* Frames can be large (hundreds of KB each)
* Storing them in SQLite or passing through multiprocessing queues would be extremely inefficient
* Workers may process tasks long after readers ingest frames
* Many tasks depend on the same frame (vehicle → plate → OCR → smooth)

Therefore frames are stored on disk, referenced by a `payload_ref`, and deleted only when the entire dependency graph has finished using them.

---

# 2. Directory Layout

Each frame is stored under a directory named after its video ID.

Example:

```
frame_store/
    video_001/
        frame_000000.npy
        frame_000001.npy
        frame_000002.npy
    video_002/
        frame_000000.npy
        ...
```

Frames are saved as `.npy` (NumPy array) for:

* Fast load/store
* No recompression
* Direct GPU consumption

The frame path is determined by:

```
(video_id, frame_idx)
```

---

# 3. payload_ref — Global Frame Identifier

The pipeline never passes raw frame pixels across processes.
Instead it passes a lightweight string:

```
payload_ref = "{video_id}_{frame_idx}"
```

All downstream tasks include:

```json
{
  "payload_ref": "video_001_123",
  "dependencies": ["video_001_123"]
}
```

This keeps SQLite small and workers efficient.

---

# 4. Saving a Frame

VideoReader calls:

```python
payload_ref = frame_store.save_frame(video_id, frame_idx, frame)
```

Internally this:

1. Ensures directory exists
2. Saves NumPy array to disk
3. Returns `payload_ref`

### Example File Saved:

```
frame_store/video_001/frame_000123.npy
```

---

# 5. Loading a Frame (Worker Side)

Workers use:

```python
frame = frame_store.load_frame(payload_ref)
```

Which:

* Parses video_id, frame_idx from string
* Loads the `.npy` file
* Returns NumPy array

Workers never touch SQLite for frame content.

---

# 6. Dependency-Based Cleanup

This system is the key innovation:

Every task includes a list:

```
"dependencies": [payload_ref_1, payload_ref_2, ...]
```

After a result is processed, the **dispatcher** asks SQLite:

> "Are there any unhandled or active tasks that depend on this frame?"

If the count is zero:

```python
frame_store.delete_frame(payload_ref)
```

This ensures:

* Frames are deleted **as soon as possible**, but never too early
* Frames used by multiple tasks persist until all dependencies finish
* Disk usage stays near minimum

---

# 7. Why Not Keep Frames in Memory?

Reasons:

* Multi-video ingestion can exceed RAM quickly
* Frames processed out-of-order require persistence
* GPU workers process slower than reading
* Worker processes cannot safely share large arrays
* Multiprocessing copies large arrays by value (expensive)

Using disk is the safest and most performant approach.

---

# 8. Failure Resilience

If the pipeline crashes:

* Frames remain on disk
* SQLite still knows remaining tasks and dependencies
* Dispatcher on the next run will delete unneeded frames

This gives the system natural crash recovery.

---

# 9. Performance Considerations

## File Format

* `.npy` is ideal for speed and fidelity
* No JPEG re-encoding overhead

## Disk I/O

* Sequential writes (good)
* Workers load frames as needed

## Cleanup Frequency

* Dispatcher performs cleanup on every result
* Constant-time existence checks

## SSD Required

For high FPS input, SSD storage is strongly recommended.

---

# 10. Future Improvements

* Use memory-mapped `.npy` files for zero-copy read
* Use a ring-buffer directory with LRU cleanups
* Compress historical frames with WebP or Zstandard
* Option for frame downsampling before storage
* Optional remote object storage (S3/minio) for distributed clusters

---

# 11. Summary

The frame store:

* Is a disk-backed, process-safe frame buffer
* Uses `payload_ref` to avoid memory blowup
* Supports dependency-based cleanup via SQLite
* Enables efficient GPU/CPU task pipelines
* Ensures frames persist only as long as needed

This system is critical for scaling the pipeline to many videos and long processing sessions.

---
