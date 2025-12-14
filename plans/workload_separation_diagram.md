# Workload Separation Visual Diagram

## Pipeline Architecture Overview

```mermaid
graph TD
    A[Dashcam Records] --> B[Indoor NAS: Raw Videos]
    B --> C[Jetson+Coral: Preprocessing]
    C --> D[4090 Machine: Heavy Processing]
    D --> E[Shed NAS: Final Archive]
    E --> F[WebUI: Display]

    style A fill:#f9f,stroke:#333
    style B fill:#fff,stroke:#333
    style C fill:#9f9,stroke:#333
    style D fill:#99f,stroke:#333
    style E fill:#ff9,stroke:#333
    style F fill:#f99,stroke:#333

    linkStyle 0 stroke:#333,stroke-width:2px;
    linkStyle 1 stroke:#333,stroke-width:2px;
    linkStyle 2 stroke:#333,stroke-width:2px;
    linkStyle 3 stroke:#333,stroke-width:2px;
    linkStyle 4 stroke:#333,stroke-width:2px;
```

## Detailed Workload Breakdown

### Jetson + Coral Preprocessing Stage

```mermaid
graph TD
    subgraph jetson[Jetson + Coral]
        A[Pull PREPROCESS_VIDEO task] --> B[Read Raw Video from NAS]
        B --> C[Extract Low-Res Frames]
        C --> D[Motion Filtering]
        D --> E[Coral Plate Detection]
        E --> F[Generate Metadata]
        F --> G[Write JSON + Thumbnails to NAS]
        G --> H[Publish HEAVY_PROCESS task]
        H --> I[Mark PREPROCESS complete]
    end

    style jetson fill:#9f9,stroke:#333
```

**Jetson Workload Details:**
- ✅ Frame extraction at reduced resolution (fast, efficient)
- ✅ Motion filtering (discards 80-95% of frames)
- ✅ Coral TPU plate region proposal (very efficient)
- ✅ Basic quality metrics (lighting, blur, confidence)
- ❌ NO full-resolution processing
- ❌ NO complex OCR or GPS alignment

### 4090 Machine Heavy Processing Stage

```mermaid
graph TD
    subgraph fourOhNinety[4090 Machine]
        A[Pull HEAVY_PROCESS task] --> B[Read Raw Video + Jetson Outputs from NAS]
        B --> C[Full-Res YOLO Detection]
        C --> D[Plate Crop Extraction]
        D --> E[GPU OCR with Confidence Voting]
        E --> F[GPS Alignment & Timestamp Mapping]
        F --> G[Best Crop/Frame Selection]
        G --> H[Metadata Consolidation]
        H --> I[Write Media to Shed NAS]
        I --> J[Publish ARCHIVAL task]
        J --> K[Mark HEAVY_PROCESS complete]
    end

    style fourOhNinety fill:#99f,stroke:#333
```

**4090 Workload Details:**
- ✅ Full-resolution YOLO detection (needs GPU power)
- ✅ High-quality plate crop extraction
- ✅ Complex OCR with multi-frame aggregation
- ✅ GPS timestamp alignment and mapping
- ✅ Final quality assurance and selection
- ❌ NO motion filtering or simple operations

---

## Workload Comparison Table

| Task | Jetson+Coral | 4090 Machine | Reason |
|------|--------------|--------------|--------|
| **Frame Extraction** | ✅ Low-res only | ❌ Not needed | Jetson can handle reduced res efficiently |
| **Motion Filtering** | ✅ Yes | ❌ No | Simple ops, huge workload reduction |
| **Plate Detection** | ✅ Coral TPU (coarse) | ❌ No | TPU optimized for this specific task |
| **Full YOLO Detection** | ❌ No | ✅ Yes | Needs 4090's GPU power and VRAM |
| **Plate Crop Extraction** | ❌ No | ✅ Yes | High-res crops need 4090 capabilities |
| **OCR Processing** | ❌ No | ✅ Yes | Complex aggregation needs compute power |
| **GPS Alignment** | ⚠️ Possible but not ideal | ✅ Yes | Better on x86 CPU with more resources |
| **Metadata Consolidation** | ❌ No | ✅ Yes | Complex structuring and QA |

---

## Data Volume Analysis

```mermaid
graph TB
    A[Raw Video: 10-20GB] --> B[Jetson Processing]
    B --> C[Preprocessed JSON: ~100KB-1MB]
    C --> D[4090 Processing]
    D --> E[Final Archive: 500MB-2GB]

    style A fill:#f96,stroke:#333
    style B fill:#9f9,stroke:#333
    style C fill:#9f9,stroke:#333
    style D fill:#99f,stroke:#333
    style E fill:#ff9,stroke:#333

    linkStyle 0 stroke:#333,stroke-width:2px;
    linkStyle 1 stroke:#333,stroke-width:2px;
    linkStyle 2 stroke:#333,stroke-width:2px;
```

**Key Data Flow Points:**
- Raw video: 10-20GB per recording (stored on Indoor NAS)
- Jetson output: ~100KB-1MB of JSON + optional thumbnails
- **Data reduction: >99% through filtering!**
- Final archive: De-resolved video + high-res plate crops

---

## Resource Utilization Heatmap

### Jetson + Coral

```mermaid
pie showData
    title Jetson + Coral Resource Usage
    "Coral TPU" : 80
    "CPU" : 40
    "GPU" : 20
    "Memory" : 50
```

### 4090 Machine

```mermaid
pie showData
    title 4090 Resource Usage
    "GPU" : 90
    "VRAM" : 85
    "CPU" : 45
    "Memory" : 60
```

---

## Processing Time Breakdown

### Without Jetson Filtering (Hypothetical)
```
Full Video Processing:
- Load & decode: 10 minutes
- Full-res YOLO: 30 minutes
- OCR processing: 20 minutes
- GPS alignment: 5 minutes
- Metadata: 5 minutes
TOTAL: ~70 minutes per video
```

### With Jetson Filtering (Current Architecture)
```
Jetson Preprocessing:
- Frame extraction: 2 minutes
- Motion filtering: 3 minutes
- Plate detection: 1 minute
- Metadata: 1 minute
TOTAL: ~7 minutes

4090 Heavy Processing:
- Load filtered data: 1 minute
- Full-res YOLO on selected frames: 5 minutes
- OCR processing: 3 minutes
- GPS alignment: 2 minutes
- Metadata: 2 minutes
TOTAL: ~13 minutes

OVERALL: ~20 minutes (70% time reduction!)
```

---

## Conclusion Diagram

```mermaid
graph LR
    A[Raw Video] --> B[Jetson Filters]
    B --> C[Filtered Data]
    C --> D[4090 Processes]
    D --> E[Final Results]

    style A fill:#f96,stroke:#333,color:white
    style B fill:#9f9,stroke:#333,color:black
    style C fill:#fff,stroke:#333
    style D fill:#99f,stroke:#333,color:white
    style E fill:#ff9,stroke:#333

    linkStyle 0 stroke:#333,stroke-width:2px;
    linkStyle 1 stroke:#333,stroke-width:2px;
    linkStyle 2 stroke:#333,stroke-width:2px;

    B -->|"Reduces workload by 80-95%"| C
    D -->|"Processes only meaningful data"| E
```

**The Key Insight:**
Jetson's role is to **filter aggressively**, removing 80-95% of unimportant frames.
4090's role is to **process accurately**, doing high-quality work on the remaining data.

This two-stage approach ensures optimal use of both devices' capabilities while maintaining reliability through the task system.
