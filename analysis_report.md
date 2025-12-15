# Dashcam Processor System Analysis Report

## 1. Overall Purpose and Goals

The dashcam processor system is designed to:
- Automatically ingest dashcam videos upon returning home
- Transform raw footage into searchable, labeled, GPS-aligned data
- Minimize storage usage through multi-stage de-resolution and selective retention
- Utilize each device for tasks it's best suited for
- Remain fully resilient to interruptions, restarts, or power loss
- Scale naturally as more hardware is added
- Provide a simple, intuitive WebUI experience

**Primary Use Case**: Process dashcam footage to create searchable plate/vehicle detection data with GPS mapping for law enforcement or private investigation purposes.

## 2. Key Architectural Components and Their Relationships

### Core Data Flow:
```
Dashcam → Indoor NAS → Jetson+Coral → 4090 Machine → Main Server → Shed NAS → WebUI
```

### Component Breakdown:

#### **Dashcam**
- Records high-resolution video files with timestamps
- Stores on SD card with optional GPS metadata
- Exposes files via Wi-Fi or removable storage
- **No processing, no uploading** - purely a data generator

#### **Indoor NAS (Ingestion Gateway)**
- Runs `viofosync` to automatically pull dashcam videos
- Stores raw videos in `/videos/raw/<trip>/`
- Notifies main server by inserting ingestion tasks
- Provides network storage for Jetson and 4090
- Holds raw videos until processing complete

#### **Jetson + Coral (Preprocessor)**
- Pulls `PREPROCESS_VIDEO` tasks from main server
- Reads raw videos from Indoor NAS
- Performs lightweight operations:
  - Low-resolution frame extraction
  - Motion filtering (discards 80-95% of frames)
  - Coral TPU-based plate region proposals
  - Basic metadata collection (lighting, blur, confidence)
- Stores temporary results locally
- Publishes `HEAVY_PROCESS_VIDEO` tasks on completion

#### **Main Server (Task Coordinator)**
- Central task scheduler and source-of-truth database
- Holds all `pending` and `complete` tasks
- Devices pull tasks autonomously (no pushing)
- Manages retries implicitly via pending tasks
- Performs light tasks: ingestion, finalization
- Orchestrates communication without tight coupling

#### **4090 Machine (Heavy Processor)**
- Pulls `HEAVY_PROCESS_VIDEO` tasks
- Performs compute-intensive operations:
  - Full-resolution YOLO detection using Jetson's region proposals
  - High-quality plate crop extraction
  - GPU-accelerated OCR with multi-frame aggregation
  - GPS timestamp alignment and coordinate mapping
  - Best crop/frame selection algorithms
  - Final metadata consolidation
- Keeps temporary data locally (NVMe SSD)
- Publishes archival tasks when finished

#### **Shed NAS (Archival Storage)**
- Long-term storage for finalized media
- Stores de-resolved videos (720p/540p)
- Stores high-resolution plate crops
- Acts as backend data provider for WebUI
- Stores metadata summaries from server

#### **WebUI (Presentation Layer)**
- Reads metadata from main server
- Reads media from Shed NAS
- Treats main server as single source of truth for metadata
- Displays:
  - Maps with GPS routes
  - Plate timelines and confidence summaries
  - Video browser
  - Frame thumbnails
  - Filter/search tools

## 3. Hardware Targets and Their Capabilities

### Dashcam
- **Type**: Dedicated recording device
- **Storage**: SD card (removable)
- **Connectivity**: Wi-Fi for file transfer
- **Processing**: None (raw capture only)

### Indoor NAS
- **Type**: Network-attached storage
- **Storage**: HDD/SSD array for raw videos
- **Software**: `viofosync` for dashcam ingestion
- **Role**: Central storage hub, ingestion gateway

### Jetson + Coral
- **CPU**: ARM-based (limited compute)
- **GPU**: Integrated graphics (moderate capability)
- **Coral TPU**: Dedicated AI accelerator
- **Memory**: 4GB RAM or less
- **Storage**: Local scratch only
- **Power**: Low-power, always-on capable
- **Strengths**:
  - Efficient edge AI inference
  - Lightweight image processing
  - Early data reduction and filtering

### Main Server
- **Type**: General-purpose server
- **DB**: Small, durable task database
- **Processing**: Task coordination only (no heavy compute)
- **Role**: Central brain of the pipeline
- **Connectivity**: Network hub for all devices

### 4090 Machine
- **GPU**: RTX 4090 (16384 CUDA cores, 24GB VRAM)
- **CPU**: Multi-core x86 processor
- **Memory**: 16GB+ system RAM
- **Storage**: Fast NVMe SSD for temporary files
- **Power**: High consumption (intermittent use)
- **Strengths**:
  - Full-resolution GPU processing
  - Complex OCR and multi-frame aggregation
  - GPS alignment algorithms
  - Final decision-making logic

### Shed NAS
- **Type**: Network-attached storage
- **Storage**: Long-term HDD/SSD array
- **Role**: Final archival destination
- **Data**: De-resolved videos + high-res plate crops

## 4. Workload Distribution Requirements

### Clear Separation of Concerns:
| Device | Role | Key Responsibilities |
|--------|------|-----------------------|
| Dashcam | Data Capture | Record raw footage, store on SD |
| Indoor NAS | Ingestion Hub | Pull videos, store raw files, notify server |
| Jetson+Coral | Preprocessor | Filter aggressively (80-95% reduction), early data reduction |
| 4090 Machine | Heavy Processor | Accurate processing on filtered data only |
| Main Server | Orchestrator | Task coordination, state management |
| Shed NAS | Archive | Long-term storage of finalized media |
| WebUI | Presentation | Display processed data to users |

### Data Flow Optimization:
- **Minimal transfer**: Jetson outputs small JSON + thumbnails (~1MB vs 10GB video)
- **No device-to-device transfer**: All data flows through NAS devices
- **Atomic completion**: Tasks marked complete only after downstream tasks published
- **Deterministic recovery**: Any device can retry failed tasks from scratch

### Workload Reduction:
- Jetson's motion filtering reduces 4090 workload by **80-95%**
- Typical video: 10,000-20,000 frames → 500-2,000 important frames
- Data volume to 4090: ~10-20GB raw → ~1MB preprocessed metadata

## 5. Web UI Integration Needs

### Metadata Requirements:
- List of videos with timestamps
- Per-video metadata (duration, plates, GPS availability)
- Plate detection data (text, confidence, location)
- GPS timelines (lat/lon, speed, bearing)
- Frame-level information for mapping

### Media Requirements:
- De-resolved archival videos (720p/540p)
- High-resolution plate crops
- Best-frame thumbnails
- Map overlays for GPS routes

### UI Features:
- **Home/Dashboard**: Recent trips, plates, events
- **Video Browser**: Date/trip organized list with metadata
- **Video Detail**: Low-res playback + GPS map + plate list
- **Plate Detail**: High-res crops + timeline + confidence breakdown
- **Map View**: All plate sightings plotted geographically
- **Search**: Plate text, date, confidence threshold, region

### API Endpoints:
- Metadata: `/videos/list`, `/videos/<id>/metadata`, `/search`
- Media: Static file serving from Shed NAS paths

## 6. Technical Constraints and Considerations

### Task System Design:
- **Pull-based execution**: Devices pull tasks, never pushed
- **Two-state model**: Only `pending` and `complete`
- **Local tasks**: Ephemeral, cleared on reboot/interruption
- **Remote tasks**: Published only after parent completion
- **No race conditions**: Atomic state transitions

### Resilience Requirements:
- **Crash-safe**: All work deterministic, can retry from scratch
- **Interruption-tolerant**: Local tasks discarded, parent remains pending
- **Power-loss recovery**: Devices simply re-pull pending tasks
- **Network failures**: Retry logic implicit in task system

### Storage Constraints:
- **Indoor NAS**: Raw videos until processing complete
- **4090 Machine**: Temporary local storage only (NVMe SSD)
- **Shed NAS**: Final archived media only (no intermediates)
- **Main Server**: Minimal metadata and task database

### Performance Considerations:
- **Jetson**: Low-power, always-on, efficient filtering
- **4090**: High-power, intermittent use, burst processing
- **Network**: High-speed LAN required for video transfers
- **Data flow**: Optimized to minimize transfers between devices

### Implementation Constraints:
- **No pushing**: All communication is pull-based
- **Atomic operations**: Tasks only marked complete after all work done
- **Minimal DB writes**: Small, durable task database on main server
- **Device autonomy**: Each device operates independently based on tasks

## 7. Summary of Key Findings

1. **Well-designed architecture** with clear separation of concerns between devices
2. **Optimal workload distribution**:
   - Jetson handles filtering and early data reduction (80-95% reduction)
   - 4090 handles accurate processing on meaningful data only
3. **Robust task system** ensures resilience through pull-based execution
4. **Efficient data flow** minimizes transfers between devices via NAS hubs
5. **Scalable design** allows adding more devices without redesign
6. **Minimal overhead** with small DB writes and simple state transitions

The architecture leverages each device's strengths:
- Jetson: Always-on filtering with Coral TPU for edge AI
- 4090: Powerful GPU processing when needed
- Main Server: Central coordination without micromanagement
- NAS devices: Reliable storage hubs throughout the pipeline

**No major architectural changes recommended** - the current design is optimal and well-suited to the stated goals of reliability, efficiency, and scalability.