# Device Adapters Implementation Summary

This document summarizes the implementation of device-specific adapters for the dashcam processor system.

## Architecture Overview

The system implements a pull-based task execution model where devices:
1. Register with the central server
2. Report their capabilities
3. Pull pending tasks matching their capabilities
4. Execute tasks locally
5. Publish new downstream tasks upon completion
6. Report status and health information

## Implemented Adapters

### 1. Abstract Device Adapter (`device_adapter.py`)
**Base class** for all device adapters with the following abstract methods:
- `get_pending_tasks()` - Pull pending tasks from server
- `mark_task_complete()` - Mark task as complete with optional downstream tasks
- `get_device_capabilities()` - Report hardware capabilities
- `health_check()` - Verify device is operational
- `_execute_task()` - Execute specific task (implementation-specific)
- `_get_downstream_tasks()` - Create downstream tasks after completion

**Key Features:**
- Pull-based execution pattern
- Task capability matching
- Error handling and recovery
- Health monitoring
- Configuration management integration

### 2. Dashcam Adapter (`dashcam_adapter.py`)
**Purpose:** Monitor and ingest dashcam footage

**Capabilities Reported:**
- Storage type (SD card)
- Video resolution
- Frame rate
- GPS enabled status
- WiFi availability

**Task Types Handled:** `INGEST_VIDEO`

**Workflow:**
1. Pulls INGEST_VIDEO tasks from server
2. Transfers video files to Indoor NAS
3. Publishes PREPROCESS_VIDEO tasks upon completion

### 3. Indoor NAS Adapter (`indoor_nas_adapter.py`)
**Purpose:** Central storage hub and ingestion gateway

**Capabilities Reported:**
- Read/write throughput (MB/s)
- Total/available storage (TB)
- SMB/NFS availability
- Mount point status

**Task Types Handled:** `INGEST_VIDEO`, `ARCHIVE_VIDEO`

**Workflow:**
1. Handles video file transfers
2. Manages storage paths and organization
3. Creates PREPROCESS_VIDEO tasks after ingestion
4. Creates ARCHIVE_VIDEO tasks for final storage

### 4. Jetson Coral Adapter (`jetson_coral_adapter.py`)
**Purpose:** Lightweight preprocessing and filtering

**Capabilities Reported:**
- Coral TPU availability (4 TOPS)
- CPU cores (quad-core ARM)
- RAM (4GB or less)
- Scratch space
- OpenCV availability

**Task Types Handled:** `PREPROCESS_VIDEO`

**Workflow:**
1. Pulls PREPROCESS_VIDEO tasks
2. Performs frame extraction at reduced resolution
3. Applies motion filtering (80-95% reduction)
4. Runs Coral TPU-based plate region proposals
5. Publishes HEAVY_PROCESS_VIDEO tasks

### 5. RTX 4090 Adapter (`rtx_4090_adapter.py`)
**Purpose:** Heavy GPU processing for full-resolution detection

**Capabilities Reported:**
- CUDA cores (16384)
- VRAM (24GB)
- CPU cores
- Scratch space
- CuDNN availability

**Task Types Handled:** `HEAVY_PROCESS_VIDEO`

**Workflow:**
1. Pulls HEAVY_PROCESS_VIDEO tasks
2. Performs full-resolution YOLO detection
3. Runs GPU-accelerated OCR with multi-frame aggregation
4. Aligns GPS timestamps and coordinates
5. Selects best crops/frames
6. Publishes ARCHIVE_VIDEO tasks

### 6. Shed NAS Adapter (`shed_nas_adapter.py`)
**Purpose:** Long-term archival storage

**Capabilities Reported:**
- Total/available storage (multi-TB)
- Read/write throughput
- HTTP server availability for file serving
- Retention policy support

**Task Types Handled:** `ARCHIVE_VIDEO`

**Workflow:**
1. Pulls ARCHIVE_VIDEO tasks
2. Stores finalized media:
   - De-resolved videos (720p/540p)
   - High-resolution plate crops
   - Best-frame thumbnails
3. Organizes by video ID and timestamp
4. Applies retention policies

## Integration Points

### Task Manager Integration
All adapters integrate with the existing [`TaskManager`](services/task_manager.py:16) class:
- Pull tasks via REST API calls
- Mark tasks complete with atomic state transitions
- Create downstream tasks as part of completion

### Device Registry Integration
Adapters work with the existing [`DeviceRegistry`](services/device_registry.py:15) system:
- Devices register with hostname and device_type
- Capabilities are reported during registration
- Health checks update device status
- Online/offline status tracking

## Error Handling & Recovery

Each adapter implements robust error handling:

1. **Network Failures:**
   - Exponential backoff for task pulls
   - Retry mechanisms for API calls
   - Graceful degradation when offline

2. **Storage Issues:**
   - Minimum threshold checks before operations
   - Warning logs when space is low
   - Preventive measures to avoid full storage

3. **Processing Errors:**
   - Task-specific error handling
   - Logging of failure reasons
   - Support for manual intervention or retry

4. **Health Monitoring:**
   - Regular health checks before task execution
   - Automatic status updates to DeviceRegistry
   - Preventive shutdown when issues detected

## Configuration Management

All adapters support device-specific configuration:

```python
{
  "server_url": "http://main-server:8000",
  "min_storage_threshold_gb": 5,
  "scratch_space_gb": 32,
  # ...device-specific settings
}
```

Configuration is passed during adapter initialization and used for:
- Server connection details
- Threshold values
- Storage paths
- Hardware limits

## Testing & Validation

Each adapter includes:
- Health check methods to validate device state
- Capability reporting for task matching
- Error recovery mechanisms
- Integration with existing services

## Data Flow

```
Dashcam → Indoor NAS (INGEST_VIDEO)
     ↓
Jetson+Coral → Main Server (PREPROCESS_VIDEO)
     ↓
RTX4090 Machine → Main Server (HEAVY_PROCESS_VIDEO)
     ↓
Shed NAS (ARCHIVE_VIDEO) → WebUI
```

## Files Created

1. `services/device_adapter.py` - Abstract base class
2. `services/dashcam_adapter.py` - Dashcam video ingestion
3. `services/indoor_nas_adapter.py` - Indoor NAS storage
4. `services/jetson_coral_adapter.py` - Jetson Coral preprocessing
5. `services/rtx_4090_adapter.py` - RTX 4090 heavy processing
6. `services/shed_nas_adapter.py` - Shed NAS archival

All adapters follow the same interface pattern defined in the abstract base class and integrate seamlessly with the existing TaskManager and DeviceRegistry services.