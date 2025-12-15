# Dashcam Processor System - Quick Start Guide

This guide provides a rapid deployment path to get the dashcam processor system up and running in under an hour.

---

## 1. Prerequisites Checklist

Before starting, ensure you have:

- ✅ **Main Server**: Linux machine (Ubuntu 20.04+) with 8GB RAM, 50GB SSD
- ✅ **Indoor NAS**: Network-attached storage accessible to all devices
- ✅ **Jetson Device**: NVIDIA Jetson Nano/Xavier with Coral TPU USB accelerator
- ✅ **RTX 4090 Machine**: Windows/Linux PC with RTX 4090 GPU and 32GB RAM
- ✅ **Shed NAS**: Secondary storage for archived videos (optional for initial testing)
- ✅ **Network**: All devices on same LAN with Gigabit Ethernet

---

## 2. 5-Minute Installation

### Step 1: Deploy Main Server

```bash
# On your main server machine
git clone https://github.com/yourorg/dashcam-processor.git
cd dashcam-processor

# Create configuration directory
sudo mkdir -p /etc/dashcam-processor/devices
cp config/config.json /etc/dashcam-processor/
cp tests/fixtures/sample_config.json /etc/dashcam-processor/devices/main-server.json

# Install dependencies
pip install fastapi uvicorn sqlalchemy python-multipart requests

# Initialize database and start server
python db/init_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     (Root path: /)
```

---

### Step 2: Set Up Indoor NAS

```bash
# On your NAS device
sudo apt-get install -y rsync smbclient

# Create shared directory
sudo mkdir -p /videos/raw /videos/preproc /videos/heavy_output
sudo chmod -R 777 /videos

# Install viofosync for automatic dashcam pull
pip install viofo-sync
cp config/viofosync.conf /etc/
nano /etc/viofosync.conf  # Configure your dashcam credentials
```

---

### Step 3: Jetson Coral Worker

```bash
# On Jetson device
git clone https://github.com/yourorg/dashcam-processor.git
cd dashcam-processor

# Create device config
cp tests/fixtures/sample_config.json /etc/dashcam-processor/devices/jetson-coral-1.json
nano /etc/dashcam-processor/devices/jetson-coral-1.json  # Set hostname and Coral path

# Install dependencies
pip install tflite-runtime opencv-python numpy requests

# Start worker
python workers/jetson_coral_worker.py --device-id jetson-coral-1
```

---

### Step 4: RTX 4090 Worker

```cmd
:: On Windows with RTX 4090
git clone https://github.com/yourorg/dashcam-processor.git
cd dashcam-processor

:: Create device config
copy tests\fixtures\sample_config.json /etc/dashcam-processor/devices/rtx-4090-1.json
:: Edit configuration with notepad to set GPU settings

:: Install dependencies in virtual environment
python -m venv venv
venv\Scripts\activate
pip install torch torchvision ultralytics easyocr opencv-python requests

:: Start worker
python workers\rtx_4090_worker.py --device-id rtx-4090-1
```

---

### Step 5: Verify System

```bash
# From any machine on the network, test the API
curl http://main-server:8000/api/v1/tasks | python -m json.tool

# Should return empty array initially:
# []

# Create a test task
curl -X POST "http://main-server:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "INGEST_VIDEO",
    "video_id": "test_video_1"
  }'

# Check devices are registering
curl http://main-server:8000/api/v1/devices | python -m json.tool
```

**Expected Results:**
- Main server responds to requests
- Jetson and RTX workers show as online in device list
- Tasks can be created and marked complete

---

## 3. Testing the Pipeline

### Manual Test Workflow

```bash
# 1. Create ingestion task (simulating dashcam upload)
echo 'Creating test video...'
curl -X POST "http://main-server:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "INGEST_VIDEO",
    "video_id": "quick_test_video"
  }'

# 2. Mark it complete and create preprocessing task
TASK_ID=$(curl http://main-server:8000/api/v1/tasks | jq -r '.[-1].task_id')
echo "Task ID: $TASK_ID"

curl -X POST "http://main-server:8000/api/v1/tasks/$TASK_ID/complete" \
  -H "Content-Type: application/json" \
  -d '{
    "new_tasks": [{
      "task_type": "PREPROCESS_VIDEO",
      "video_id": "quick_test_video"
    }]
  }'

# 3. Check Jetson pulled the task
sleep 5
curl http://main-server:8000/api/v1/tasks?state=pending | python -m json.tool

# Should show PREPROCESS_VIDEO task as pending (Jetson will pull it)

echo "Pipeline test completed!"
```

---

## 4. Production Readiness Checklist

Before using with real dashcam footage:

- [ ] **Security**: Enable HTTPS with Let's Encrypt
- [ ] **Backups**: Set up daily database backups
- [ ] **Monitoring**: Configure health checks and alerts
- [ ] **Storage**: Verify NAS paths are accessible from all devices
- [ ] **Permissions**: Set proper file permissions on shared storage
- [ ] **Network**: Test bandwidth between devices (should be ≥100 Mbps)

---

## 5. Common Issues and Fixes

| Issue | Symptom | Solution |
|-------|---------|----------|
| Workers not connecting | Empty device list in API | Check firewall rules, verify server is reachable |
| Tasks stuck pending | Tasks never get pulled | Restart worker processes, check logs |
| Permission denied | File access errors | `chmod -R 777 /videos` on NAS temporarily for testing |
| GPU not detected | RTX worker fails to start | Verify CUDA drivers installed correctly |

---

## 6. Next Steps

After successful quick start:

1. **Review full deployment guide** in [`docs/deployment_guide.md`](docs/deployment_guide.md)
2. **Configure device settings** for optimal performance
3. **Set up monitoring** as described in [`docs/operations.md`](docs/operations.md)
4. **Explore API documentation** in [`docs/api_reference.md`](docs/api_reference.md)

---

## 7. Support

For issues not covered here:
- Check logs: `/var/log/dashcam/server.log` (or worker log files)
- Review [troubleshooting section](docs/operations.md#5-troubleshooting-common-issues) in operations guide
- Contact support with:
  - Server version (`git rev-parse HEAD`)
  - Log snippets showing the error
  - Device types and configurations

---

## 8. Expected Performance

With this minimal setup:

| Stage | Processing Time |
|-------|-----------------|
| Ingestion | <1 minute |
| Preprocessing (Jetson) | 5-30 minutes per video |
| Heavy Processing (RTX 4090) | 30-120 minutes per video |
| Archival | <5 minutes |

Actual times depend on:
- Video length and resolution
- Network bandwidth between devices
- Hardware specifications

---

## 9. Cleanup After Testing

```bash
# Remove test tasks
curl -X DELETE "http://main-server:8000/api/v1/tasks?video_id=test_video_1"

# Or wipe entire database (use with caution)
rm tasks.db
python db/init_db.py
```

---

## 10. Success Criteria

You've successfully completed quick start when:

✅ Main server is running and accessible
✅ At least one Jetson worker is online
✅ At least one RTX 4090 worker is online
✅ Tasks can be created and marked complete
✅ Workers pull tasks automatically

**Estimated time to completion: 30-60 minutes**

---

## Need More Help?

Consult the detailed documentation:
- [`docs/deployment_guide.md`](docs/deployment_guide.md) - Full deployment instructions
- [`docs/configuration_reference.md`](docs/configuration_reference.md) - Configuration options
- [`docs/operations.md`](docs/operations.md) - Monitoring and maintenance
- [`docs/api_reference.md`](docs/api_reference.md) - API endpoints

Or check the example configurations in `config/` directory.