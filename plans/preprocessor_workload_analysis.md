# Preprocessor vs. Heavy Processing Workload Analysis

## Executive Summary

This document analyzes the workload separation between the Jetson+Coral preprocessor and the 4090 machine in the dashcam processing pipeline. The goal is to clearly define what tasks belong on each device based on their capabilities, ensuring optimal resource utilization and efficient processing flow.

---

## Device Capabilities Overview

### Jetson + Coral (Preprocessor)
- **CPU**: ARM-based processor (limited compute power)
- **GPU**: Integrated graphics (moderate capability)
- **Coral TPU**: Dedicated AI accelerator for edge inference
- **Memory**: Limited RAM (typically 4GB or less)
- **Storage**: Local scratch space only
- **Network**: Ethernet-connected to Indoor NAS
- **Power**: Low-power, always-on capable

### 4090 Machine (Heavy Processing)
- **GPU**: RTX 4090 (high-end, 16384 CUDA cores, 24GB VRAM)
- **CPU**: Multi-core x86 processor
- **Memory**: Large system RAM (16GB+)
- **Storage**: Fast NVMe SSD for temporary files
- **Network**: High-speed LAN connection
- **Power**: High-power consumption, typically used intermittently

---

## Current Workload Distribution Analysis

### Jetson + Coral Responsibilities (Preprocessing Stage)

Based on the documentation, the Jetson currently performs:

1. **Frame Extraction**
   - Low-resolution frame extraction from raw video
   - Full framerate but reduced resolution for efficiency

2. **Motion Filtering**
   - Frame delta or optical flow analysis
   - Discards consecutive frames with no movement
   - Identifies frames with meaningful structure
   - Filters out too dark/too blurry frames

3. **Coral Plate Region Proposal**
   - MobileNet/SSD model on Coral TPU
   - Generates coarse bounding boxes for possible license plates
   - Very cheap to run per-frame
   - Outputs JSON list of candidate regions + optional thumbnails

4. **Metadata Heuristics**
   - Lighting level estimation
   - Blur/clarity scoring
   - Frame confidence composite calculation
   - Frame rejection reasons (for debugging)

5. **Task Management**
   - Pulls PREPROCESS_VIDEO tasks from main server
   - Publishes HEAVY_PROCESS_VIDEO tasks upon completion

### 4090 Machine Responsibilities (Heavy Processing Stage)

The 4090 currently performs:

1. **Full-Resolution YOLO Detection**
   - High-accuracy YOLO model on selected frames
   - Uses Jetson's region proposals to limit search space
   - Detects: license plates, vehicles, optional features

2. **Plate Crop Extraction**
   - High-resolution plate crops from full frames
   - Temporary storage in local SSD folder

3. **GPU-Accelerated OCR**
   - EasyOCR GPU mode on each plate crop
   - Multi-candidate aggregation
   - Confidence voting across multiple frames

4. **GPS Timestamp Alignment**
   - Loads GPS log/sidecar data
   - Maps frame index → GPS coordinate via interpolation
   - Produces per-frame GPS metadata (lat/lon, speed, bearing)

5. **Best Crop & Frame Selection**
   - Chooses best-quality crops for each plate
   - Selects representative frames for WebUI

6. **Metadata Consolidation**
   - Creates final structured data with:
     - Full timelines across frames
     - Confidence scores
     - Movement vectors
     - GPS positions
     - Detection summaries

---

## Workload Separation Rationale

### Why Certain Tasks Belong on Jetson + Coral

1. **Low-Resolution Processing**
   - Frame extraction at reduced resolution is ideal for the Jetson's limited GPU
   - Reduces data volume early in the pipeline
   - Minimizes network transfer to 4090

2. **Motion Filtering**
   - Simple image processing operations
   - Dramatically reduces number of frames needing full processing
   - Saves significant 4090 compute time

3. **Coral TPU Accelerated Tasks**
   - Plate region proposal is perfect for Coral TPU
   - TPU excels at specific AI inference tasks
   - Much more efficient than running on x86/CPU

4. **Early Data Reduction**
   - Jetson's role is to filter and reduce data volume
   - Only meaningful frames proceed to 4090
   - Reduces 4090 workload by 80-95% (estimated)

### Why Certain Tasks Belong on 4090 Machine

1. **High-Resolution Processing**
   - Full-resolution YOLO requires significant GPU memory
   - RTX 4090's VRAM is essential for high-res inference
   - Jetson would struggle with full HD frames

2. **Complex OCR Tasks**
   - GPU-accelerated OCR benefits from 4090's compute power
   - Multi-candidate aggregation requires significant processing
   - Confidence voting across multiple frames is compute-intensive

3. **GPS Alignment Complexity**
   - Timestamp interpolation and coordinate mapping
   - Requires loading and processing GPS logs
   - Better suited for x86 architecture

4. **Final Decision Making**
   - Best crop/frame selection algorithms
   - Metadata consolidation and structuring
   - Quality assurance before archival

5. **Memory-Intensive Operations**
   - Loading full video frames into GPU memory
   - Temporary storage of intermediate crops
   - Processing large batches of data

---

## Proposed Workload Optimization

### Tasks That Should Definitely Stay on Jetson + Coral

✅ **Frame Extraction (Low-Res)**
- Continue extracting at reduced resolution
- Store locally during processing
- Transfer minimal data to 4090

✅ **Motion Filtering**
- Keep all motion detection algorithms on Jetson
- This is the most valuable filtering step
- Reduces downstream workload significantly

✅ **Coral Plate Region Proposal**
- This is the Coral TPU's sweet spot
- Fast, efficient inference
- Small output size (JSON + thumbnails)

✅ **Basic Metadata Collection**
- Lighting, blur, confidence scores
- Simple heuristics that don't require heavy compute

### Tasks That Should Definitely Stay on 4090 Machine

✅ **Full-Resolution YOLO Detection**
- Requires RTX 4090's GPU power
- High-resolution frame processing
- Complex model inference

✅ **Plate Crop Extraction & OCR**
- GPU-accelerated OCR needs 4090
- Multi-frame confidence aggregation
- Quality plate recognition requires compute

✅ **GPS Timestamp Alignment**
- Complex interpolation algorithms
- Coordinate mapping operations
- Better suited for x86/CPU

✅ **Final Metadata Consolidation**
- Decision-making logic
- Quality assurance
- Final output preparation

### Edge Cases & Potential Optimizations

**Questionable Tasks (Could Be Re-evaluated):**

1. **Frame Extraction Resolution**
   - Current: Low-res on Jetson, full-res on 4090
   - Alternative: Could Jetson extract at slightly higher res?
   - Tradeoff: More data transfer vs. better quality for motion detection

2. **Motion Filtering Complexity**
   - Current: Simple frame delta/optical flow
   - Alternative: Could use more sophisticated algorithms?
   - Constraint: Must remain efficient on Jetson hardware

3. **Plate Region Proposal Output**
   - Current: JSON + optional thumbnails
   - Alternative: Could reduce thumbnail resolution further?
   - Tradeoff: Quality vs. transfer size

**Not Recommended Optimizations:**

- ❌ Moving full-resolution processing to Jetson (hardware limitation)
- ❌ Running OCR on Jetson (Coral TPU not suited for OCR)
- ❌ Doing GPS alignment on Jetson (complex math, better on x86)

---

## Data Flow Optimization

### Current Data Flow
```
Dashcam → Indoor NAS → [Jetson Preprocessing] → Indoor NAS → [4090 Heavy Processing] → Shed NAS
```

### Optimized Data Flow Considerations

1. **Minimize Data Transfer Between Devices**
   - Jetson should output only essential metadata
   - Avoid transferring full frames when possible
   - Use efficient serialization (JSON, binary formats)

2. **Leverage Indoor NAS as Temporary Storage**
   - Jetson writes preprocessed artifacts to NAS
   - 4090 reads from same location
   - No direct device-to-device transfer needed

3. **Atomic Task Completion**
   - Jetson marks task complete only after publishing downstream task
   - Ensures 4090 always has required inputs available

---

## Performance Considerations

### Jetson + Coral Bottlenecks
- Limited RAM may constrain batch processing
- Integrated GPU limits high-resolution work
- Coral TPU is fast but has specific use cases (not general-purpose)

### 4090 Machine Advantages
- Massive VRAM for high-resolution frames
- Fast NVMe storage for temporary files
- x86 CPU for complex algorithms
- High-speed LAN for data transfer

---

## Recommendations

### What Should Run on Jetson + Coral (Preprocessor)
1. Low-resolution frame extraction
2. Motion filtering and frame selection
3. Coral TPU-based plate region proposals
4. Basic image quality metrics (lighting, blur, confidence)
5. Preprocessed metadata generation (JSON format)

### What Should Run on 4090 Machine (Heavy Processing)
1. Full-resolution YOLO detection using Jetson's region proposals
2. High-quality plate crop extraction
3. GPU-accelerated OCR with multi-frame aggregation
4. GPS timestamp alignment and coordinate mapping
5. Best crop/frame selection algorithms
6. Final metadata consolidation and structuring

### Implementation Guidelines

1. **Ensure Jetson outputs are minimal and efficient:**
   - Small JSON files with region proposals
   - Low-resolution thumbnails only when necessary
   - Compressed data formats where possible

2. **Leverage the Coral TPU to its fullest:**
   - Keep plate detection models optimized for TPU
   - Batch processing where possible within Jetson's limits
   - Minimize CPU-GPU transfers

3. **Design 4090 tasks to be self-contained:**
   - Each task should have all inputs specified in task metadata
   - Temporary files cleaned up automatically
   - Failure recovery through task re-pulling

4. **Monitor and optimize data transfer sizes:**
   - Track size of preprocessed artifacts
   - Compress where beneficial without losing quality
   - Consider binary formats for numerical data

---

## Conclusion

The current workload separation is well-designed and takes advantage of each device's strengths:

- **Jetson + Coral**: Fast, efficient preprocessing with early data reduction
- **4090 Machine**: Powerful heavy processing on meaningful data only

The key insight is that the Jetson's role is to **filter aggressively** while the 4090's role is to **process accurately**. This two-stage approach ensures optimal use of both devices' capabilities while maintaining the pipeline's resilience and efficiency.

No major changes are recommended to the current architecture. The separation of concerns is appropriate, and each device performs tasks it is best suited for based on its hardware capabilities.