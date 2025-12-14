# Decision Guide: Jetson+Coral vs. 4090 Machine Workload Separation

## Executive Summary

Based on a thorough analysis of the architecture documentation, here's what should run on each device and why:

### **Jetson + Coral (Preprocessor) - What Goes Here**

✅ **Frame Extraction at Low Resolution**
- Extract frames at full framerate but reduced resolution
- Ideal for Jetson's limited GPU capabilities
- Reduces decoding cost and data volume

✅ **Motion Filtering**
- Frame delta or optical flow analysis
- Discards consecutive frames with no movement
- Identifies frames with meaningful structure
- Filters out too dark/too blurry frames
- *This is the MOST valuable filtering step - can reduce downstream workload by 80-95%*

✅ **Coral TPU Plate Region Proposal**
- MobileNet/SSD model specifically optimized for Coral TPU
- Generates coarse bounding boxes for possible license plates
- Very efficient (cheap to run per-frame)
- Outputs JSON list of candidate regions + optional thumbnails

✅ **Basic Metadata Collection**
- Lighting level estimation
- Blur/clarity scoring
- Frame confidence composite calculation
- Frame rejection reasons (for debugging)

### **4090 Machine (Heavy Processing) - What Goes Here**

✅ **Full-Resolution YOLO Detection**
- High-accuracy YOLO model on selected frames
- Uses Jetson's region proposals to limit search space
- Detects license plates, vehicles, and other objects
- *Requires 4090's GPU power and VRAM*

✅ **Plate Crop Extraction**
- Extracts high-resolution plate crops from full frames
- Stores crops in temporary local SSD folder
- Keeps only minimal set needed for OCR and final archival

✅ **GPU-Accelerated OCR with Multi-Frame Aggregation**
- EasyOCR GPU mode on each plate crop
- Multi-candidate aggregation
- Confidence voting across multiple frames
- Plate stabilization through temporal analysis

✅ **GPS Timestamp Alignment & Coordinate Mapping**
- Loads GPS log or sidecar data
- Performs timestamp-based interpolation
- Maps frame index → GPS coordinate
- Produces per-frame GPS metadata (lat/lon, speed, bearing)

✅ **Best Crop and Frame Selection**
- Chooses best-quality crop for each detected plate
- Selects representative frames for WebUI display
- Implements quality assurance checks

✅ **Final Metadata Consolidation**
- Creates comprehensive structured data
- Aggregates confidence scores
- Calculates movement vectors
- Compiles detection summaries
- Prepares final output for archival

---

## Decision Rationale

### Why These Tasks Belong on Jetson + Coral

1. **Hardware Match:**
   - Coral TPU is specifically designed for edge AI inference
   - Low-resolution frame processing fits Jetson's GPU capabilities
   - Motion filtering uses simple image operations perfect for ARM CPU

2. **Efficiency:**
   - Early data reduction minimizes downstream workload
   - Small output size (JSON + thumbnails) reduces network transfer
   - Low power consumption allows always-on operation

3. **Pipeline Benefits:**
   - Aggressive filtering ensures 4090 only processes meaningful frames
   - Deterministic, restartable processing through task system
   - Clean separation of concerns between devices

### Why These Tasks Belong on 4090 Machine

1. **Hardware Requirements:**
   - Full-resolution YOLO needs RTX 4090's GPU power and VRAM
   - Complex OCR with multi-frame aggregation requires significant compute
   - GPS alignment algorithms better suited to x86 architecture

2. **Quality Assurance:**
   - Final decision-making logic belongs here
   - High-quality plate recognition needs compute resources
   - Metadata consolidation requires more CPU/memory

3. **Usage Pattern:**
   - High-power device can run overnight when not in use
   - Burst processing mode matches typical user behavior
   - Temporary local storage on fast NVMe SSD

---

## What Should NOT Be Moved Between Devices

### ❌ Do NOT Move Full-Resolution Processing to Jetson
- Jetson's integrated GPU cannot handle high-res frames efficiently
- Limited VRAM would cause performance issues
- Would defeat the purpose of having a powerful 4090 machine

### ❌ Do NOT Run OCR on Jetson/Coral TPU
- Coral TPU is optimized for detection, not recognition
- OCR requires different neural network architecture
- Multi-frame aggregation needs x86 CPU resources

### ❌ Do NOT Move GPS Alignment to Jetson
- Complex interpolation algorithms better suited to x86
- Requires loading and processing GPS logs efficiently
- More memory-intensive than Jetson can handle comfortably

---

## Implementation Recommendations

### For Maximum Efficiency:

1. **Jetson Configuration:**
   - Keep frame extraction resolution as low as possible while maintaining feature detection quality
   - Optimize Coral TPU models specifically for plate region proposal
   - Implement aggressive motion filtering thresholds
   - Minimize output data size (compact JSON, compressed thumbnails)

2. **4090 Configuration:**
   - Batch process multiple videos overnight
   - Utilize GPU to maximum capacity during processing runs
   - Keep temporary files on fast NVMe SSD
   - Clean up aggressively after task completion

3. **Data Flow Optimization:**
   - Jetson writes preprocessed artifacts directly to Indoor NAS
   - 4090 reads from same location (no direct device-to-device transfer)
   - Use efficient serialization formats (JSON, binary where appropriate)

---

## Expected Performance Benefits

With this workload separation:

| Metric | Without Jetson Filtering | With Jetson Filtering |
|--------|--------------------------|-----------------------|
| Frames Processed by 4090 | All frames (10,000-20,000) | Only important frames (500-2,000) |
| Data Volume to 4090 | Full video files | Small JSON metadata (~1MB) |
| 4090 Processing Time | Hours per video | Minutes per video |
| Power Consumption | High (always-on 4090) | Low (Jetson always-on, 4090 intermittent) |
| Storage Requirements | High (keep all frames) | Low (only keep filtered results) |

**Result:** 70-80% reduction in overall processing time and resources!

---

## Final Answer to Your Question

### What Belongs on the Preprocessor (Jetson + Coral):
1. **Low-resolution frame extraction** - Jetson can handle this efficiently
2. **Motion filtering** - Critical for workload reduction (discards 80-95% of frames)
3. **Coral TPU plate region proposal** - This is what the Coral TPU was made for
4. **Basic image quality metrics** - Simple heuristics that don't need heavy compute

### What Belongs on the Main Workhorse (4090 Machine):
1. **Full-resolution YOLO detection** - Needs 4090's GPU power and VRAM
2. **Plate crop extraction** - High-res crops require 4090 capabilities
3. **GPU-accelerated OCR** - Complex processing with multi-frame aggregation
4. **GPS alignment** - Better on x86 CPU with more resources
5. **Final metadata consolidation** - Decision-making and quality assurance

### Key Insight:
The architecture is already optimally designed! The Jetson's role is to **filter aggressively**, removing unimportant frames early in the pipeline. The 4090's role is to **process accurately**, doing high-quality work on only the meaningful data that remains.

**No major changes needed** - the current separation leverages each device's strengths perfectly.