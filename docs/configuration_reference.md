# Dashcam Processor System - Configuration Reference

This document provides detailed information about all configuration options in the dashcam processor system.

---

## 1. Global Configuration Options

Global settings are stored in `/etc/dashcam-processor/config.json` and apply to the entire system.

### `global.task_retry_delay_seconds`

- **Type**: Integer
- **Default**: `300` (5 minutes)
- **Description**: Delay between task retries when a device is unavailable. This prevents immediate retry storms.
- **Example**:
  ```json
  "task_retry_delay_seconds": 600
  ```

### `global.max_concurrent_tasks_per_device`

- **Type**: Integer
- **Default**: `1`
- **Description**: Maximum number of tasks a single device can execute simultaneously. Set to `1` for most embedded devices.
- **Example**:
  ```json
  "max_concurrent_tasks_per_device": 2
  ```

### `global.storage_retention_days`

Configuration for automatic cleanup of intermediate files.

#### `storage_retention_days.raw_videos`
- **Type**: Integer
- **Default**: `90` days
- **Description**: How long to keep raw video files on Indoor NAS after processing completes

#### `storage_retention_days.preproc_data`
- **Type**: Integer
- **Default**: `30` days
- **Description**: How long to keep preprocessing outputs before deletion

#### `storage_retention_days.heavy_output`
- **Type**: Integer
- **Default**: `7` days
- **Description**: How long to keep heavy processing temporary files

**Example**:
```json
"storage_retention_days": {
  "raw_videos": 90,
  "preproc_data": 30,
  "heavy_output": 7
}
```

---

## 2. Storage Paths Configuration

Storage paths define where files are stored across the distributed system.

### `storage_paths.indoor_nas`

Configuration for Indoor NAS storage locations.

#### `storage_paths.indoor_nas.base`
- **Type**: String
- **Default**: `"//nas-1/videos/"`
- **Description**: Base UNC path to Indoor NAS

#### `storage_paths.indoor_nas.raw`
- **Type**: String
- **Default**: `"raw/"`
- **Description**: Subdirectory for raw video files

#### `storage_paths.indoor_nas.preproc`
- **Type**: String
- **Default**: `"preproc/"`
- **Description**: Subdirectory for preprocessing outputs

#### `storage_paths.indoor_nas.heavy_output`
- **Type**: String
- **Default**: `"heavy_output/"`
- **Description**: Subdirectory for heavy processing temporary files

**Example**:
```json
"indoor_nas": {
  "base": "//nas-1/videos/",
  "raw": "raw/",
  "preproc": "preproc/",
  "heavy_output": "heavy_output/"
}
```

### `storage_paths.shed_nas`

Configuration for Shed NAS archival storage.

#### `storage_paths.shed_nas.archive_base`
- **Type**: String
- **Default**: `"//shed-nas/archive/"`
- **Description**: Base UNC path to archived videos and plate crops

**Example**:
```json
"shed_nas": {
  "archive_base": "//shed-nas/archive/"
}
```

---

## 3. Device-Specific Configuration

Each device has its own configuration file in `/etc/dashcam-processor/devices/{device-id}.json`.

### Common Device Settings

#### `hostname`
- **Type**: String
- **Required**: Yes
- **Description**: Unique hostname/identifier for the device

#### `device_type`
- **Type**: String
- **Required**: Yes
- **Valid values**: `"jetson_coral"`, `"rtx_4090"`, `"indoor_nas"`, `"shed_nas"`
- **Description**: Type of device

**Example**:
```json
{
  "hostname": "jetson-coral-1",
  "device_type": "jetson_coral"
}
```

---

## 4. Jetson Coral Device Configuration

### `storage.local_scratch`
- **Type**: String
- **Default**: `"/tmp/jetson_scratch"`
- **Description**: Local directory for temporary processing files

### `storage.max_concurrent_tasks`
- **Type**: Integer
- **Default**: `1`
- **Description**: Maximum concurrent preprocessing tasks

### `coral.device_path`
- **Type**: String
- **Required**: Yes
- **Description**: USB device path for Coral TPU (e.g., `/dev/bus/usb/001/003`)

**Complete Example**:
```json
{
  "hostname": "jetson-coral-1",
  "device_type": "jetson_coral",
  "storage": {
    "local_scratch": "/tmp/jetson_scratch",
    "max_concurrent_tasks": 1
  },
  "coral": {
    "device_path": "/dev/bus/usb/001/003"
  }
}
```

---

## 5. RTX 4090 Device Configuration

### `gpu.device_id`
- **Type**: Integer
- **Default**: `0`
- **Description**: CUDA device ID (usually 0 for single GPU systems)

### `gpu.max_batch_size`
- **Type**: Integer
- **Default**: `1`
- **Description**: Number of videos to process simultaneously

### `gpu.yolo_model_path`
- **Type**: String
- **Required**: Yes
- **Description**: Path to YOLOv8 model file (`.pt`)

### `gpu.ocr_model`
- **Type**: String
- **Default**: `"en"`
- **Description**: OCR language model

### `storage.local_scratch`
- **Type**: String
- **Required**: Yes
- **Description**: Local directory for temporary GPU processing files (must have ~20GB free)

**Complete Example**:
```json
{
  "hostname": "rtx-4090-1",
  "device_type": "rtx_4090",
  "gpu": {
    "device_id": 0,
    "max_batch_size": 1,
    "yolo_model_path": "./models/yolov8n.pt",
    "ocr_model": "en"
  },
  "storage": {
    "local_scratch": "D:\\dashcam_temp",
    "max_concurrent_tasks": 1
  }
}
```

---

## 6. Processing Parameters

Processing parameters control how videos are processed at each stage.

### Preprocessing Parameters (Jetson)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `frame_extraction_rate` | `0.5` | Frames per second to extract (reduces from 30fps) |
| `motion_threshold` | `0.15` | Minimum motion delta to keep frame |
| `plate_detection_confidence` | `0.6` | Coral TPU confidence threshold for plate proposals |
| `max_frames_per_video` | `5000` | Maximum frames to process per video |

**Example**:
```json
"preprocessing": {
  "frame_extraction_rate": 0.2,
  "motion_threshold": 0.1,
  "plate_detection_confidence": 0.7,
  "max_frames_per_video": 3000
}
```

### Heavy Processing Parameters (RTX 4090)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `yolo_confidence_threshold` | `0.5` | YOLO detection confidence threshold |
| `ocr_confidence_threshold` | `0.7` | OCR character confidence threshold |
| `min_plate_width` | `40` | Minimum plate width in pixels |
| `max_plate_height` | `120` | Maximum plate height in pixels |

**Example**:
```json
"heavy_processing": {
  "yolo_confidence_threshold": 0.6,
  "ocr_confidence_threshold": 0.8,
  "min_plate_width": 50,
  "max_plate_height": 100
}
```

---

## 7. Task-Specific Configuration

### Device Capabilities Requirements

Tasks can specify required device capabilities:

```json
{
  "task_type": "HEAVY_PROCESS_VIDEO",
  "device_capabilities_required": {
    "gpu_vram_gb": 16,
    "cpu_cores": 8,
    "storage_gb": 500
  }
}
```

### Task Priorities

Tasks can have priority levels (stored in metadata):

```json
{
  "task_type": "PREPROCESS_VIDEO",
  "metadata": {
    "priority": "high",  // low, normal, high, critical
    "notes": "Urgent processing required"
  }
}
```

---

## 8. Example Complete Configuration

### Global Configuration (`config.json`)
```json
{
  "global": {
    "task_retry_delay_seconds": 300,
    "max_concurrent_tasks_per_device": 1,
    "storage_retention_days": {
      "raw_videos": 90,
      "preproc_data": 30,
      "heavy_output": 7
    }
  },
  "devices": {},
  "storage_paths": {
    "indoor_nas": {
      "base": "//nas-1/videos/",
      "raw": "raw/",
      "preproc": "preproc/",
      "heavy_output": "heavy_output/"
    },
    "shed_nas": {
      "archive_base": "//shed-nas/archive/"
    }
  }
}
```

### Jetson Coral Device (`devices/jetson-coral-1.json`)
```json
{
  "hostname": "jetson-coral-1",
  "device_type": "jetson_coral",
  "storage": {
    "local_scratch": "/tmp/jetson_scratch",
    "max_concurrent_tasks": 1
  },
  "coral": {
    "device_path": "/dev/bus/usb/001/003"
  },
  "preprocessing": {
    "frame_extraction_rate": 0.5,
    "motion_threshold": 0.15,
    "plate_detection_confidence": 0.6
  }
}
```

### RTX 4090 Device (`devices/rtx-4090-1.json`)
```json
{
  "hostname": "rtx-4090-1",
  "device_type": "rtx_4090",
  "gpu": {
    "device_id": 0,
    "max_batch_size": 2,
    "yolo_model_path": "./models/yolov8n.pt",
    "ocr_model": "en"
  },
  "storage": {
    "local_scratch": "D:\\dashcam_temp",
    "max_concurrent_tasks": 1
  },
  "heavy_processing": {
    "yolo_confidence_threshold": 0.5,
    "ocr_confidence_threshold": 0.7,
    "min_plate_width": 40,
    "max_plate_height": 120
  }
}
```

---

## 9. Configuration Validation

Validate all configurations before applying:

```bash
# Validate global configuration
python scripts/validate_config.py /etc/dashcam-processor/config.json

# Validate device configurations
python scripts/validate_config.py /etc/dashcam-processor/devices/
```

Common validation errors:
- Missing required fields (hostname, device_type)
- Invalid UNC paths
- Insufficient storage allocations
- Conflicting task priorities

---

## 10. Dynamic Configuration Updates

The configuration system supports runtime updates:

```python
from config.loader import ConfigurationLoader

config_loader = ConfigurationLoader()

# Update global setting
config_loader.update_global_config({
  "global": {
    "task_retry_delay_seconds": 600
  }
})

# Update device setting
config_loader.update_device_config("jetson-coral-1", {
  "storage": {
    "max_concurrent_tasks": 2
  }
})
```

**Important**: Some changes require worker restart to take effect.

---

## 11. Configuration Best Practices

### General Guidelines

1. **Start conservative**: Use default values initially, then tune based on performance
2. **Document changes**: Add comments explaining why specific values were chosen
3. **Version control**: Track configuration changes in git or similar system
4. **Backup before changes**: Always backup configurations before making changes

### Performance Tuning Tips

1. **Jetson Devices**:
   - Start with `frame_extraction_rate=0.2` and increase if processing is too slow
   - Monitor CPU temperature; reduce load if thermal throttling occurs

2. **RTX 4090 Machines**:
   - Test batch sizes starting from 1, then 2
   - Ensure GPU has enough VRAM for batch size × expected frames
   - Reduce `max_plate_height` to improve OCR accuracy on small plates

3. **Storage**:
   - Monitor free space daily during initial deployment
   - Adjust retention periods based on actual storage usage patterns
   - Consider separate storage for raw vs processed data if possible

---

## 12. Troubleshooting Configuration Issues

### Common Problems and Solutions

| Problem | Symptoms | Solution |
|---------|----------|----------|
| Invalid JSON syntax | Worker fails to start, error in logs | Use `jq` or online validator to check JSON syntax |
| Missing device config | Device not showing in registry | Ensure config file exists with correct permissions |
| Path resolution errors | Tasks fail with "file not found" | Verify UNC paths are accessible from all devices |
| Permission denied | Worker can't write to scratch dir | Check directory ownership: `chown -R user:group /path` |

### Debugging Configuration

Enable debug logging to see configuration loading:

```bash
python -v workers/jetson_coral_worker.py --log-level DEBUG 2>&1 | grep -i config
```

Check effective configuration in worker code:
```python
device_config = self.config_loader.get_device_config(self.device_id)
print(json.dumps(device_config, indent=2))
```

---

## 13. Configuration Templates

### Minimal Jetson Configuration
```json
{
  "hostname": "jetson-coral-2",
  "device_type": "jetson_coral",
  "coral": {
    "device_path": "/dev/bus/usb/001/004"
  }
}
```

### High-Performance RTX 4090 Configuration
```json
{
  "hostname": "rtx-4090-performance",
  "device_type": "rtx_4090",
  "gpu": {
    "device_id": 0,
    "max_batch_size": 3,
    "yolo_model_path": "./models/yolov8l.pt"
  },
  "storage": {
    "local_scratch": "/mnt/ssd/dashcam_temp",
    "max_concurrent_tasks": 1
  }
}
```

---

## 14. Migration Guide

### Migrating from Version 1 to Version 2

1. **Backup existing configurations**:
   ```bash
   cp -r /etc/dashcam-processor /etc/dashcam-processor.backup.$(date +%Y%m%d)
   ```

2. **Update global config** (new fields added):
   ```json
   {
     "global": {
       "task_retry_delay_seconds": 300,
       "max_concurrent_tasks_per_device": 1,
       "storage_retention_days": {
         "raw_videos": 90,
         "preproc_data": 30,
         "heavy_output": 7
       }
     }
   }
   ```

3. **Update device configs** (new required fields):
   - Add `device_type` field if missing
   - Verify all storage paths exist

4. **Test with validation script**:
   ```bash
   python scripts/validate_config.py --strict /etc/dashcam-processor/
   ```

---

## 15. Reference Tables

### Task Types and Their Capabilities

| Task Type | Typical Device | Required GPU VRAM | Estimated Time |
|-----------|---------------|------------------|----------------|
| INGEST_VIDEO | Indoor NAS | None | <1 min |
| PREPROCESS_VIDEO | Jetson Coral | 2GB | 5-30 min |
| HEAVY_PROCESS_VIDEO | RTX 4090 | 8-16GB | 30-120 min |
| ARCHIVE_VIDEO | Shed NAS | None | <5 min |

### Storage Requirements by Device

| Device Type | Local Storage | Network Storage |
|-------------|---------------|-----------------|
| Main Server | 50GB+ SSD | Read-only access to NAS |
| Indoor NAS | Multiple TB (raw videos) | None |
| Jetson Coral | 32GB microSD/SSD | Access to Indoor NAS |
| RTX 4090 | 512GB NVMe SSD | Access to Indoor & Shed NAS |
| Shed NAS | Multiple TB (archive) | None |

---

## 16. Configuration Schema

For programmatic validation, the system uses this schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "global": {
      "type": "object",
      "properties": {
        "task_retry_delay_seconds": {"type": "integer", "minimum": 60},
        "max_concurrent_tasks_per_device": {"type": "integer", "minimum": 1, "maximum": 5},
        "storage_retention_days": {
          "type": "object",
          "properties": {
            "raw_videos": {"type": "integer", "minimum": 7},
            "preproc_data": {"type": "integer", "minimum": 1},
            "heavy_output": {"type": "integer", "minimum": 1}
          },
          "required": ["raw_videos", "preproc_data", "heavy_output"]
        }
      },
      "required": ["task_retry_delay_seconds", "max_concurrent_tasks_per_device", "storage_retention_days"]
    },
    "devices": {
      "type": "object"
    },
    "storage_paths": {
      "type": "object",
      "properties": {
        "indoor_nas": {
          "type": "object",
          "properties": {
            "base": {"type": "string"},
            "raw": {"type": "string"},
            "preproc": {"type": "string"},
            "heavy_output": {"type": "string"}
          },
          "required": ["base", "raw", "preproc", "heavy_output"]
        },
        "shed_nas": {
          "type": "object",
          "properties": {
            "archive_base": {"type": "string"}
          },
          "required": ["archive_base"]
        }
      },
      "required": ["indoor_nas", "shed_nas"]
    }
  },
  "required": ["global", "storage_paths"]
}
```

This schema is used by the validation script to ensure configuration integrity.