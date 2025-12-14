# Workload Separation Analysis: Jetson+Coral vs. 4090 Machine

## Executive Summary

This document provides a detailed analysis of how to separate the preprocessor (Jetson+Coral) from the main workhorse (4090 machine) in the dashcam processing pipeline. Based on the architecture documentation, I've identified what tasks are best suited for each device based on their hardware capabilities and the system's design goals.

---

## Current Architecture Overview

The pipeline follows a clear linear flow:

```
Dashcam → Indoor NAS → Jetson+Coral → 4090 Machine → Shed NAS → WebUI
```

Each device has well-defined responsibilities that leverage its strengths:
- **Jetson+Coral**: Lightweight preprocessing and filtering
- **4090 Machine**: Heavy GPU processing and finalization
- **Main Server**: Task coordination and state management

---

## Device Capability Analysis

### Jetson + Coral Strengths
✅ Low-power, always-on capable
✅ Integrated Coral TPU for efficient AI inference
✅ Good for lightweight image processing
✅ Ethernet-connected to storage
✅ Ideal for early data reduction and filtering

### Jetson + Coral Limitations
❌ Limited RAM (typically 4GB)
❌ Weak integrated GPU (not suitable for high-res work)
❌ Slow CPU compared to x86
❌ Small local storage capacity

### 4090 Machine Strengths
✅ Massive GPU compute power (RTX 4090)
✅ Large VRAM (24GB) for high-resolution processing
✅ Fast NVMe SSD storage
✅ Multi-core x86 CPU
✅ High-speed network connection

### 4090 Machine Limitations
❌ High power consumption (not ideal for always-on)
❌ Typically used intermittently
❌ Requires more maintenance than embedded devices

---

## Task Classification Matrix

| Task Category | Jetson + Coral Suitability | 4090 Machine Suitability | Rationale |
|--------------|----------------------------|---------------------------|----------|
| **Low-Resolution Frame Extraction** | ✅ HIGH | ❌ LOW | Jetson can handle reduced-res frames efficiently. No need for 4090's power. |
| **Motion Filtering** | ✅ HIGH | ❌ LOW | Simple image processing, perfect for Jetson. Dramatically reduces workload. |
| **Coral Plate Region Proposal** | ✅ HIGH | ❌ LOW | Coral TPU excels at this specific AI task. Very efficient. |
| **High-Resolution YOLO Detection** | ❌ LOW | ✅ HIGH | Requires 4090's GPU power and VRAM for full HD frames. |
| **Plate Crop Extraction** | ❌ LOW | ✅ HIGH | High-res crops need 4090's capabilities. |
| **GPU-Accelerated OCR** | ❌ LOW | ✅ HIGH | Complex OCR with multi-frame aggregation needs 4090. |
| **GPS Timestamp Alignment** | ⚠️ MEDIUM | ✅ HIGH | Could run on Jetson but better on x86 CPU. Low priority for optimization. |
| **Best Crop Selection** | ⚠️ MEDIUM | ✅ HIGH | Decision-making logic better suited to 4090's architecture. |
| **Metadata Consolidation** | ❌ LOW | ✅ HIGH | Complex structuring and quality assurance tasks. |

---

## Recommended Workload Separation

### What Should Run on Jetson + Coral (Preprocessor)

**Primary Responsibilities:**
1. **Frame Extraction at Reduced Resolution**
   - Extract frames at full framerate but low resolution
   - Store locally during processing
   - Transfer minimal data to 4090 machine

2. **Motion Filtering and Frame Selection**
   - Implement frame delta or optical flow analysis
   - Discard consecutive frames with no movement
   - Identify frames with meaningful structure
   - Filter out too dark/too blurry frames
   - *This is the most valuable filtering step - can reduce 4090 workload by 80-95%*

3. **Coral TPU-Based Plate Region Proposal**
   - Run MobileNet/SSD model on Coral TPU
   - Generate coarse bounding boxes for possible license plates
   - Output JSON list of candidate regions
   - Include optional low-resolution thumbnails

4. **Basic Image Quality Metrics**
   - Lighting level estimation
   - Blur/clarity scoring
   - Frame confidence composite calculation
   - Frame rejection reasons (for debugging)

**Outputs from Jetson:**
- Small JSON files with region proposals and metadata
- Optional low-resolution thumbnails (only when beneficial)
- Compressed data formats where possible

### What Should Run on 4090 Machine (Heavy Processing)

**Primary Responsibilities:**
1. **Full-Resolution YOLO Detection**
   - High-accuracy YOLO model on selected frames
   - Use Jetson's region proposals to limit search space
   - Detect license plates, vehicles, and other objects

2. **High-Quality Plate Crop Extraction**
   - Extract high-resolution plate crops from full frames
   - Store crops in temporary local SSD folder
   - Keep only the minimal set needed for OCR and final archival

3. **GPU-Accelerated OCR with Multi-Frame Aggregation**
   - Run EasyOCR GPU mode on each plate crop
   - Perform multi-candidate aggregation
   - Implement confidence voting across multiple frames
   - Stabilize plate readings through temporal analysis

4. **GPS Timestamp Alignment and Coordinate Mapping**
   - Load GPS log or sidecar data
   - Perform timestamp-based interpolation
   - Map frame index → GPS coordinate
   - Produce per-frame GPS metadata (lat/lon, speed, bearing)

5. **Best Crop and Frame Selection Algorithms**
   - Choose the best-quality crop for each detected plate
   - Select representative frames for WebUI display
   - Implement quality assurance checks

6. **Final Metadata Consolidation**
   - Create comprehensive structured data for each plate and vehicle
   - Include full timelines across frames
   - Aggregate confidence scores
   - Calculate movement vectors
   - Compile detection summaries
   - Prepare final output for archival

**Outputs from 4090:**
- Finalized metadata (stored in main server DB)
- De-resolved video files (sent to Shed NAS)
- High-resolution plate crops (sent to Shed NAS)

---

## Optimization Recommendations

### For Jetson + Coral

1. **Maximize Early Data Reduction**
   - Aggressively filter out unimportant frames
   - Reduce resolution as much as possible while maintaining feature detection quality
   - Minimize the data volume sent to 4090 machine

2. **Leverage Coral TPU Effectively**
   - Keep plate detection models optimized for TPU
   - Batch processing where possible within Jetson's memory limits
   - Minimize CPU-GPU transfers between Jetson and Coral

3. **Efficient Output Formatting**
   - Use compact JSON or binary formats for metadata
   - Compress thumbnail images
   - Only include essential information in outputs

4. **Local Scratch Management**
   - Keep temporary files local during processing
   - Clean up immediately after task completion
   - Ensure all scratch is deleted on reboot/interruption

### For 4090 Machine

1. **Batch Processing Optimization**
   - Process multiple videos in sequence overnight
   - Utilize GPU to maximum capacity when running
   - Implement smart queueing based on system load

2. **Temporary Storage Strategy**
   - Use fast NVMe SSD for intermediate files
   - Keep temporary data local during processing
   - Clean up aggressively after task completion

3. **Quality Threshold Tuning**
   - Adjust confidence thresholds based on real-world results
   - Balance accuracy with processing time
   - Implement adaptive algorithms that learn from previous runs

4. **Task Prioritization**
   - Run heavy tasks during off-hours when machine is idle
   - Implement pause/resume for user interactivity
   - Provide progress feedback for long-running operations

---

## Data Flow Optimization

### Current Flow (Optimal)
```
1. Dashcam records → Indoor NAS stores raw videos
2. Jetson pulls PREPROCESS_VIDEO task from main server
3. Jetson reads raw video from Indoor NAS
4. Jetson performs lightweight preprocessing locally
5. Jetson writes small preprocessed artifacts to Indoor NAS
6. Jetson publishes HEAVY_PROCESS_VIDEO task
7. 4090 pulls heavy processing task
8. 4090 reads raw video and Jetson outputs from Indoor NAS
9. 4090 performs heavy GPU processing locally
10. 4090 writes final media to Shed NAS
11. 4090 publishes archival task
```

### Key Optimization Points

✅ **Minimal Data Transfer**: Jetson outputs are small (JSON + optional thumbnails)
✅ **No Device-to-Device Transfer**: All data flows through Indoor NAS/Shed NAS
✅ **Atomic Task Completion**: Tasks only marked complete after downstream tasks published
✅ **Deterministic Recovery**: Any device can retry failed tasks from scratch

---

## Performance Impact Analysis

### Estimated Workload Reduction

| Metric | Before Jetson Filtering | After Jetson Filtering |
|--------|-------------------------|-----------------------|
| Total Frames per Video | 10,000-20,000 | 500-2,000 (80-95% reduction) |
| Data Volume to 4090 | ~10-20GB video + metadata | ~100KB-1MB preprocessed JSON |
| 4090 Processing Time | Hours per video | Minutes per video |

### Resource Utilization

**Jetson + Coral:**
- CPU: Moderate (30-50% during processing)
- GPU: Low (integrated graphics, minimal load)
- Coral TPU: High (80-90% utilization for plate detection)
- Memory: Moderate (2-3GB typical)
- Storage: Minimal (scratch only)

**4090 Machine:**
- GPU: High (80-90% during heavy processing)
- CPU: Moderate (for OCR and metadata tasks)
- VRAM: High (10-20GB for full-res frames)
- Memory: Moderate (4-8GB typical)
- Storage: Temporary (NVMe SSD usage)

---

## Conclusion

The current workload separation in the architecture is **well-designed and optimal**. Each device performs tasks that match its hardware capabilities:

### Jetson + Coral: The Filter
- **Role**: Early data reduction and lightweight preprocessing
- **Strengths**: Efficient at filtering, Coral TPU for specific AI tasks
- **Output**: Small metadata files identifying promising frames/regions

### 4090 Machine: The Accurate Processor
- **Role**: High-quality processing on filtered data
- **Strengths**: Powerful GPU for full-resolution work, x86 CPU for complex algorithms
- **Output**: Finalized detections, OCR results, ready-for-archive media

### No Major Changes Recommended

The architecture already implements the optimal separation:
- Jetson handles what it's good at: filtering and early reduction
- 4090 handles what it's good at: high-quality full-resolution processing
- The task system ensures resilience and proper sequencing

**Minor optimizations could include:**
1. Further reducing thumbnail resolution in Jetson outputs
2. Tuning motion detection thresholds for better filtering
3. Compressing JSON metadata where appropriate
4. Implementing batch processing on 4090 for multiple videos

But these are refinements rather than architectural changes.

---

## Final Recommendation

**Keep the current workload separation as-is.** The architecture is correctly designed with:
- Jetson + Coral doing lightweight preprocessing and filtering
- 4090 Machine doing heavy GPU processing on filtered data
- Main Server coordinating everything through pull-based tasks

This division of labor ensures:
✅ Optimal hardware utilization
✅ Maximum reliability through task system
✅ Efficient data flow with minimal transfer
✅ Scalability by adding more devices

The only potential improvements are in the implementation details (threshold tuning, compression), not in the architectural separation itself.