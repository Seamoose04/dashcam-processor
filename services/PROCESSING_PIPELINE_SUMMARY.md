# Processing Pipeline Components - Implementation Summary

This document summarizes the implementation of the core processing pipeline components for the dashcam processor system.

## Implemented Services

### 1. Ingestion Service [`services/ingestion_service.py`](services/ingestion_service.py)
- **Purpose**: Monitor indoor NAS for new video files and create ingestion tasks
- **Key Features**:
  - Scans video directories for MP4, AVI, MOV files
  - Creates `INGEST_VIDEO` tasks in the task database
  - Extracts basic file metadata (size, timestamps)
  - Handles continuous monitoring with configurable intervals

### 2. Preprocessor Service [`services/preprocessor.py`](services/preprocessor.py)
- **Purpose**: Lightweight processing on Jetson Coral with Coral TPU
- **Key Features**:
  - Pulls `PREPROCESS_VIDEO` tasks from task manager
  - Performs frame extraction at reduced resolution (640x480 by default)
  - Implements motion filtering (80-95% frame reduction)
  - Uses Coral TPU for plate region proposals
  - Collects quality metrics and generates thumbnails
  - Publishes `HEAVY_PROCESS_VIDEO` tasks upon completion

### 3. Heavy Processor Service [`services/heavy_processor.py`](services/heavy_processor.py)
- **Purpose**: Full-resolution GPU processing on RTX 4090
- **Key Features**:
  - Pulls `HEAVY_PROCESS_VIDEO` tasks from task manager
  - Performs full-resolution YOLO detection using Jetson proposals
  - GPU-accelerated OCR with multi-frame aggregation
  - GPS timestamp alignment and coordinate mapping
  - Best crop/frame selection algorithms
  - Generates high-resolution plate crops
  - Publishes `ARCHIVE_VIDEO` tasks upon completion

### 4. Archival Service [`services/archival_service.py`](services/archival_service.py)
- **Purpose**: Long-term storage on shed NAS
- **Key Features**:
  - Pulls `ARCHIVE_VIDEO` tasks from task manager
  - Stores finalized media:
    - De-resolved videos (simulated as placeholders)
    - High-resolution plate crops
    - Detection metadata
  - Implements retention policy cleanup
  - Provides static file references for WebUI

## Integration with Task System

All services integrate with the existing task system:

1. **Pull-based Execution**: Services pull tasks from the central task database
2. **State Management**: Tasks transition from `pending` to `complete`
3. **Downstream Task Creation**: Each service creates appropriate downstream tasks:
   - Ingestion → Preprocessing
   - Preprocessing → Heavy Processing
   - Heavy Processing → Archival

## Configuration Integration

All services use the configuration system:
- Global settings in `/etc/dashcam-processor/config.json`
- Device-specific settings in `/etc/dashcam-processor/devices/<hostname>.json`
- Storage paths for indoor NAS and shed NAS
- Processing parameters (resolutions, thresholds, etc.)

## Error Handling

All services implement robust error handling:
- Automatic retry logic with exponential backoff
- Graceful failure modes
- Comprehensive logging
- Task completion even on errors (with error flags)

## Data Flow

The complete pipeline flow:

```
Dashcam → Indoor NAS → Ingestion Service
       → Preprocessor (Jetson Coral) → Heavy Processor (RTX 4090)
       → Archival Service (Shed NAS) → WebUI
```

## Usage Examples

Each service can be run directly with the main block:

```bash
# Run ingestion service
python services/ingestion_service.py

# Run preprocessor on Jetson Coral
python services/preprocessor.py

# Run heavy processor on RTX 4090
python services/heavy_processor.py

# Run archival service on shed NAS
python services/archival_service.py
```

## Testing Notes

The implementations include mock functionality for:
- Coral TPU inference (simulated detections)
- YOLO model processing (simulated results)
- OCR plate reading (generated realistic-looking plates)

For production use, these should be replaced with actual model integrations.

## Next Steps

1. Integrate actual model files (`plate.pt`, `yolov8n.pt`) into the services
2. Add unit tests for each service
3. Implement integration tests for end-to-end workflows
4. Set up monitoring and metrics collection
5. Deploy to actual devices (Jetson Coral, RTX 4090, NAS systems)