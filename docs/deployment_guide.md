# Dashcam Processor System - Deployment Guide

This document provides comprehensive instructions for deploying the dashcam processor system across all device types.

---

## 1. System Overview and Architecture

The dashcam processor system is a distributed pipeline designed to process raw dashcam footage into searchable, labeled data. The architecture consists of:

```
Dashcam → Indoor NAS → Jetson+Coral → Main Server → 4090 Machine → Shed NAS → WebUI
```

### Key Components:
- **Main Server**: Central coordinator and task database
- **Indoor NAS**: Ingestion gateway and intermediate storage
- **Jetson + Coral TPU**: Lightweight preprocessing and filtering
- **RTX 4090 Machine**: Heavy GPU processing (YOLO, OCR, GPS alignment)
- **Shed NAS**: Final archival storage for WebUI media
- **WebUI**: Interactive interface for browsing processed footage

### Core Principles:
- **Pull-based execution**: Devices pull tasks from the main server rather than receiving pushed work
- **Deterministic processing**: Tasks can be safely retried without duplication
- **Resilience to interruptions**: System recovers gracefully from crashes or power loss
- **Minimal storage overhead**: Intermediate data is cleaned up automatically

---

## 2. Hardware Requirements

### Main Server
| Requirement | Specification |
|-------------|---------------|
| CPU         | Quad-core Intel/AMD (or better) |
| RAM         | 8GB minimum, 16GB recommended |
| Storage     | 50GB+ SSD for database and metadata |
| OS          | Linux (Ubuntu 20.04+ recommended) |
| Network     | Gigabit Ethernet, stable connection |

### Indoor NAS
| Requirement | Specification |
|-------------|---------------|
| CPU         | Dual-core or better |
| RAM         | 4GB minimum |
| Storage     | Multiple TB for raw videos (RAID recommended) |
| OS          | Linux-based NAS OS (Synology, TrueNAS, etc.) |
| Network     | Gigabit Ethernet, always-on |

### Jetson + Coral TPU
| Requirement | Specification |
|-------------|---------------|
| Device      | NVIDIA Jetson Nano or Xavier NX |
| Accelerator | USB Coral TPU (Edge TPU) |
| Storage     | 32GB+ microSD card or SSD |
| RAM         | 4GB (Jetson Nano) or 8GB (Xavier NX) |
| OS          | JetPack 4.6+ for Jetson devices |

### RTX 4090 Machine
| Requirement | Specification |
|-------------|---------------|
| GPU         | NVIDIA RTX 4090 (or equivalent) |
| CPU         | Intel i7/i9 or Ryzen 7/9 (8+ cores) |
| RAM         | 32GB minimum, 64GB recommended for heavy workloads |
| Storage     | 512GB NVMe SSD for temporary processing |
| OS          | Windows 10/11 or Linux with CUDA drivers |
| Power       | Stable 850W+ PSU (GPU power requirements) |

### Shed NAS
| Requirement | Specification |
|-------------|---------------|
| CPU         | Quad-core Intel/AMD |
| RAM         | 8GB minimum |
| Storage     | Multiple TB for archival (RAID-Z recommended) |
| OS          | Linux-based NAS OS |
| Network     | Gigabit Ethernet, always-on |

---

## 3. Software Dependencies

### Main Server
```bash
# Required packages
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv sqlite3 nginx certbot

# Python dependencies (requirements.txt)
fastapi==0.95.2
uvicorn==0.22.0
sqlalchemy==2.0.15
pydantic==1.10.7
python-multipart==0.0.6
requests==2.31.0
```

### Indoor NAS
```bash
# Required for viofosync and file operations
sudo apt-get install -y python3 python3-pip rsync smbclient

# Python dependencies (requirements.txt)
viofo-sync==1.2.0
requests==2.31.0
```

### Jetson + Coral TPU
```bash
# NVIDIA JetPack components
sudo apt-get install -y python3-pip libedgetpu1-std

# Python dependencies (requirements.txt)
tflite-runtime==2.10.0  # For Coral TPU
opencv-python==4.7.0.72
numpy==1.23.5
requests==2.31.0
```

### RTX 4090 Machine
```bash
# NVIDIA drivers and CUDA
sudo apt-get install -y nvidia-driver-525 nvidia-cuda-toolkit

# Python dependencies (requirements.txt)
torch==2.0.1
torchvision==0.15.2
ultralytics==8.0.143  # YOLOv8
easyocr==1.7.0
opencv-python==4.7.0.72
numpy==1.23.5
requests==2.31.0
```

### Shed NAS
```bash
# File serving and backup tools
sudo apt-get install -y samba nfs-kernel-server rsync cron
```

---

## 4. Installation Steps

### Step 1: Set Up Configuration Directory
Create the configuration directory structure on each device:

```bash
sudo mkdir -p /etc/dashcam-processor/devices
sudo chown -R $USER:$USER /etc/dashcam-processor
```

Copy the sample configuration:
```bash
cp config/config.json /etc/dashcam-processor/
cp config/devices/* /etc/dashcam-processor/devices/
```

### Step 2: Install Main Server

1. **Clone repository**:
   ```bash
   git clone https://github.com/yourorg/dashcam-processor.git
   cd dashcam-processor
   ```

2. **Create Python virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Initialize database**:
   ```bash
   python db/init_db.py
   ```

4. **Start server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Set up as systemd service** (production):
   ```bash
   sudo cp scripts/dashcam-server.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable dashcam-server
   sudo systemctl start dashcam-server
   ```

### Step 3: Install Indoor NAS Worker

1. **Install dependencies**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3 python3-pip rsync smbclient
   pip3 install viofo-sync requests
   ```

2. **Configure viofosync** (edit `/etc/viofosync.conf`):
   ```ini
   [dashcam]
   username = your_username
   password = your_password
   local_path = /videos/raw/
   sync_interval = 300
   ```

3. **Set up ingestion script**:
   ```bash
   sudo cp scripts/ingestion_trigger.sh /usr/local/bin/
   sudo chmod +x /usr/local/bin/ingestion_trigger.sh
   ```

4. **Start viofosync service**:
   ```bash
   sudo systemctl enable viofosync
   sudo systemctl start viofosync
   ```

### Step 4: Install Jetson Coral Worker

1. **Flash Jetson device** with JetPack 4.6+
2. **Install Python environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure device-specific settings** (edit `/etc/dashcam-processor/devices/jetson-coral-1.json`):
   ```json
   {
     "storage": {
       "local_scratch": "/tmp/jetson_scratch",
       "max_concurrent_tasks": 1
     },
     "coral": {
       "device_path": "/dev/bus/usb/001/003"
     }
   }
   ```

4. **Start worker**:
   ```bash
   python workers/jetson_coral_worker.py --device-id jetson-coral-1
   ```

### Step 5: Install RTX 4090 Worker

1. **Install NVIDIA drivers and CUDA** (follow official NVIDIA instructions)
2. **Set up Python environment**:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install torch torchvision ultralytics easyocr opencv-python requests
   ```

3. **Configure GPU settings** (edit `/etc/dashcam-processor/devices/rtx-4090-1.json`):
   ```json
   {
     "gpu": {
       "device_id": 0,
       "max_batch_size": 2,
       "yolo_model_path": "./models/yolov8n.pt",
       "ocr_model": "en"
     },
     "storage": {
       "local_scratch": "D:\\dashcam_temp",
       "max_concurrent_tasks": 1
     }
   }
   ```

4. **Start worker** (Windows):
   ```cmd
   venv\Scripts\activate
   python workers\rtx_4090_worker.py --device-id rtx-4090-1
   ```

### Step 6: Install Shed NAS Worker

1. **Set up storage directories**:
   ```bash
   sudo mkdir -p /archive
   sudo chown -R $USER:$USER /archive
   ```

2. **Configure Samba/NFS sharing** (edit `/etc/samba/smb.conf`):
   ```ini
   [archive]
     path = /archive
     browseable = yes
     read only = no
     guest ok = no
     valid users = @dashcam-users
   ```

3. **Start worker**:
   ```bash
   python workers/shed_nas_worker.py --device-id shed-nas-1
   ```

---

## 5. Configuration Setup

### Global Configuration (config.json)

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

### Device-Specific Configuration Examples

#### Jetson Coral:
```json
{
  "device_type": "jetson_coral",
  "hostname": "jetson-coral-1",
  "storage": {
    "local_scratch": "/tmp/jetson_scratch",
    "max_concurrent_tasks": 1
  },
  "coral": {
    "device_path": "/dev/bus/usb/001/003"
  }
}
```

#### RTX 4090:
```json
{
  "device_type": "rtx_4090",
  "hostname": "rtx-4090-1",
  "gpu": {
    "device_id": 0,
    "max_batch_size": 2,
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

## 6. Security Considerations

### Network Security
- Use VLANs to separate dashcam network from main LAN
- Enable firewall rules on all devices:
  ```bash
  sudo ufw allow from 192.168.1.0/24 to any port 8000
  sudo ufw enable
  ```

### Authentication
- Secure API endpoints with JWT authentication
- Use HTTPS for all communications (obtain certificates via Let's Encrypt):
  ```bash
  sudo certbot --nginx -d dashcam.yourdomain.com
  ```

### Data Protection
- Encrypt sensitive data at rest (database encryption)
- Implement proper file permissions:
  ```bash
  chmod 700 /etc/dashcam-processor/
  chown -R dashcam-user:dashcam-group /archive
  ```

### Monitoring and Logging
- Centralize logs using ELK stack or similar
- Set up log rotation:
  ```bash
  sudo cp scripts/logrotate.conf /etc/logrotate.d/dashcam
  ```

---

## 7. Initial Setup Verification

After deployment, verify the system:

1. **Check server status**:
   ```bash
   curl http://localhost:8000/api/v1/tasks | python -m json.tool
   ```

2. **Test device communication**:
   ```bash
   # From Jetson:
   curl -X POST "http://main-server:8000/api/v1/devices/heartbeat" \
     -H "Content-Type: application/json" \
     -d '{"hostname": "jetson-coral-1", "device_type": "jetson_coral"}'
   ```

3. **Validate configuration**:
   ```bash
   python scripts/validate_config.py /etc/dashcam-processor/
   ```

4. **Run health check**:
   ```bash
   python scripts/health_check.py --server http://main-server:8000