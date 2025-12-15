# Dashcam Processor System - Operational Procedures

This document covers day-to-day operations, monitoring, maintenance, and troubleshooting for the dashcam processor system.

---

## 1. System Startup and Shutdown Sequences

### Normal Startup Sequence

1. **Indoor NAS** (first to start)
   ```bash
   sudo systemctl start viofosync
   sudo systemctl start smbd
   ```

2. **Main Server**
   ```bash
   sudo systemctl start dashcam-server
   sudo systemctl start nginx
   ```

3. **Jetson Coral Devices** (can start in any order)
   ```bash
   python workers/jetson_coral_worker.py --device-id jetson-coral-1
   ```

4. **RTX 4090 Machines**
   ```cmd
   venv\Scripts\activate
   python workers\rtx_4090_worker.py --device-id rtx-4090-1
   ```

5. **Shed NAS** (last to start)
   ```bash
   sudo systemctl start smbd
   python workers/shed_nas_worker.py --device-id shed-nas-1
   ```

### Graceful Shutdown Sequence

1. **RTX 4090 Machines** (first to stop - allows in-progress tasks to complete)
   ```cmd
   # Send SIGINT to worker process
   Ctrl+C
   ```

2. **Jetson Coral Devices**
   ```bash
   pkill -f jetson_coral_worker.py
   ```

3. **Main Server** (wait for all pending tasks to clear)
   ```bash
   sudo systemctl stop dashcam-server
   ```

4. **Indoor NAS**
   ```bash
   sudo systemctl stop viofosync
   ```

5. **Shed NAS** (last to stop)
   ```bash
   sudo systemctl stop smbd
   ```

---

## 2. Monitoring and Alerting Setup

### Basic Monitoring Commands

```bash
# Check task queue status
curl http://main-server:8000/api/v1/tasks?state=pending | python -m json.tool | jq '.[] | {task_id, task_type, created_at}'

# Check device status
curl http://main-server:8000/api/v1/devices | python -m json.tool

# Check system health
python scripts/health_check.py --server http://main-server:8000
```

### Prometheus/Grafana Monitoring (Recommended)

1. **Install Prometheus**:
   ```bash
   sudo apt-get install prometheus
   ```

2. **Configure scrape config** (`/etc/prometheus/prometheus.yml`):
   ```yaml
   global:
     scrape_interval: 15s

   scrape_configs:
     - job_name: 'dashcam-server'
       static_configs:
         - targets: ['main-server:8000']
   ```

3. **Create custom metrics endpoint** in `api/routes/webui.py`:
   ```python
   @router.get("/metrics")
   async def get_metrics():
       from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
       return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
   ```

4. **Install Grafana dashboards**:
   - Import dashboard for task queue monitoring
   - Set up alerts for:
     - Tasks stuck in pending state (>24 hours)
     - Devices offline for extended periods
     - Storage thresholds exceeded

### Alerting Rules

| Metric | Threshold | Action |
|--------|-----------|--------|
| Pending tasks count | >10 per device type | Investigate worker availability |
| Task age (pending) | >24 hours | Manual intervention required |
| Device offline duration | >1 hour | Check device connectivity |
| Indoor NAS free space | <10% | Archive old videos manually |
| Shed NAS free space | <5% | Expand storage immediately |

---

## 3. Backup and Restore Procedures

### Database Backup

```bash
# Daily backup script (cron: 0 2 * * *)
BACKUP_DIR="/backups/dashcam"
mkdir -p $BACKUP_DIR

# SQLite backup
sqlite3 /var/lib/dashcam/tasks.db ".backup $BACKUP_DIR/tasks_$(date +%Y%m%d).db"

# Compress and rotate
tar czf $BACKUP_DIR/tasks_$(date +%Y%m%d).tar.gz $BACKUP_DIR/tasks_$(date +%Y%m%d).db
rm $BACKUP_DIR/tasks_$(date +%Y%m%d).db

# Keep last 30 days
find $BACKUP_DIR -name "tasks_*.tar.gz" -mtime +30 -delete
```

### Configuration Backup

```bash
# Back up all configurations (cron: 0 3 * * *)
CONFIG_DIR="/etc/dashcam-processor"
BACKUP_DIR="/backups/config"

rsync -av $CONFIG_DIR/ $BACKUP_DIR/
tar czf $BACKUP_DIR/config_$(date +%Y%m%d).tar.gz $BACKUP_DIR/devices/
```

### Restore Procedure

1. **Stop all services**:
   ```bash
   sudo systemctl stop dashcam-server viofosync smbd
   ```

2. **Restore database** (from backup):
   ```bash
   sqlite3 tasks.db < tasks_20240101.db
   ```

3. **Verify task integrity**:
   ```bash
   python scripts/validate_tasks.py
   ```

4. **Start services in order**:
   ```bash
   sudo systemctl start dashcam-server viofosync smbd
   ```

---

## 4. Scaling Guidance for Production

### Adding More Jetson Devices

1. **Prepare new Jetson device** with same OS and dependencies
2. **Create unique device ID**: `jetson-coral-2`
3. **Copy configuration template**:
   ```bash
   cp /etc/dashcam-processor/devices/jetson-coral-1.json /etc/dashcam-processor/devices/jetson-coral-2.json
   ```
4. **Update hostname in config**:
   ```json
   {
     "hostname": "jetson-coral-2",
     "device_type": "jetson_coral"
   }
   ```
5. **Start worker** on new device

### Adding More RTX 4090 Machines

1. **Install GPU drivers and CUDA** on new machine
2. **Create device configuration**:
   ```bash
   cp /etc/dashcam-processor/devices/rtx-4090-1.json /etc/dashcam-processor/devices/rtx-4090-2.json
   ```
3. **Update configuration** with new GPU settings:
   ```json
   {
     "hostname": "rtx-4090-2",
     "device_type": "rtx_4090",
     "gpu": {
       "device_id": 0,
       "max_batch_size": 1  # Start conservative
     }
   }
   ```
4. **Start worker**

### Storage Scaling

| Device | Scaling Strategy |
|--------|------------------|
| Indoor NAS | Add RAID array, expand existing storage |
| Shed NAS | Migrate to object storage (S3-compatible) or add archive tier with cold storage |
| Main Server | Increase SSD capacity for database growth |

---

## 5. Troubleshooting Common Issues

### Task Stuck in Pending State

**Symptoms**: Tasks remain pending despite devices being online

**Diagnosis**:
```bash
# Check which tasks are pending
curl http://main-server:8000/api/v1/tasks?state=pending | python -m json.tool

# Check device capabilities
curl http://main-server:8000/api/v1/devices | python -m json.tool
```

**Solutions**:
1. Verify devices can reach the server:
   ```bash
   ping main-server
   curl -v http://main-server:8000/api/v1/tasks/pending
   ```
2. Check device capabilities match task requirements:
   ```python
   # Compare task.device_capabilities_required with device.capabilities
   ```
3. Restart worker processes

### Device Not Registering

**Symptoms**: Device doesn't appear in device list

**Diagnosis**:
```bash
# Check if heartbeats are working
tail -f /var/log/dashcam/worker.log
```

**Solutions**:
1. Verify network connectivity to main server
2. Check firewall rules:
   ```bash
   sudo ufw status
   ```
3. Restart worker with debug logging:
   ```bash
   python workers/jetson_coral_worker.py --device-id jetson-coral-1 --log-level DEBUG
   ```

### Storage Space Issues

**Symptoms**: Tasks fail with "No space left" errors

**Diagnosis**:
```bash
# Check storage on all devices
df -h | grep -E '(/|/archive|/videos)'

# Check task failures
curl http://main-server:8000/api/v1/tasks?state=failed
```

**Solutions**:
1. **Indoor NAS**: Run cleanup script:
   ```bash
   python scripts/cleanup_raw_videos.py --days 90
   ```
2. **RTX 4090 local storage**: Clear scratch directory:
   ```bash
   rm -rf /tmp/dashcam_temp/*
   ```
3. **Shed NAS**: Archive old videos to cold storage

### Task Processing Failures

**Symptoms**: Tasks marked as failed or repeatedly retrying

**Diagnosis**:
```bash
# Get task details
curl http://main-server:8000/api/v1/tasks/12345 | python -m json.tool

# Check worker logs on specific device
journalctl -u dashcam-worker --no-pager | grep "task 12345"
```

**Common Causes and Solutions**:

| Error Type | Cause | Solution |
|------------|-------|----------|
| Video file not found | NAS path changed or video deleted | Verify paths in task inputs, restore from backup if needed |
| GPU out of memory | Task too large for available VRAM | Reduce batch size, split task manually |
| Coral TPU disconnected | USB connection issue | Replug device, check dmesg for errors |
| Network timeout | NAS unavailable during processing | Implement retry logic with exponential backoff |

### Performance Issues

**Symptoms**: Slow processing times, tasks taking longer than expected

**Diagnosis**:
```bash
# Check system load on workers
top -c | grep python

# Monitor network throughput
iftop -i eth0
```

**Solutions**:
1. **Network bottlenecks**: Verify Gigabit Ethernet is working:
   ```bash
   ethtool eth0 | grep Speed
   ```
2. **CPU contention**: Check if other processes are using resources:
   ```bash
   htop
   ```
3. **GPU utilization**: On RTX 4090, check CUDA usage:
   ```bash
   nvidia-smi
   ```

---

## 6. Maintenance Schedule

| Task | Frequency | Responsible Party |
|------|-----------|-------------------|
| Database backup | Daily (2 AM) | System Admin |
| Configuration backup | Daily (3 AM) | System Admin |
| Log rotation | Weekly | System Admin |
| Health check | Hourly | Monitoring system |
| Storage capacity check | Daily | Monitoring system |
| Task queue review | Weekly | Operations team |
| Device firmware updates | Quarterly | Device owners |
| Model version updates | Monthly | ML team |

---

## 7. Emergency Procedures

### Database Corruption

1. **Stop all services immediately**:
   ```bash
   sudo systemctl stop dashcam-server viofosync smbd
   ```

2. **Restore from latest backup**:
   ```bash
   sqlite3 tasks.db < /backups/dashcam/tasks_$(date -d "1 day ago" +%Y%m%d).db
   ```

3. **Verify integrity**:
   ```bash
   python scripts/validate_tasks.py --repair
   ```

4. **Start services in order** (as shown in startup sequence)

### Critical Storage Failure

1. **Stop ingestion immediately**:
   ```bash
   sudo systemctl stop viofosync
   ```

2. **Pause heavy processing**:
   - Stop RTX 4090 workers
   - Mark tasks as paused in database

3. **Free up space**:
   - Delete oldest raw videos first
   - Archive processed videos to Shed NAS manually if possible
   - Consider temporary storage expansion

### Security Incident

1. **Isolate affected devices** from network
2. **Rotate credentials**:
   ```bash
   # Update API keys and passwords
   python scripts/rotate_credentials.py --new-password "secure-password-$(date +%s)"
   ```
3. **Review logs** for unauthorized access:
   ```bash
   grep -E '401|403|authentication' /var/log/nginx/*.log
   ```
4. **Re-deploy with updated security patches**

---

## 8. Performance Tuning

### Jetson Optimization

- Reduce frame extraction rate in preprocessing
- Adjust motion filtering thresholds to reduce false positives
- Limit concurrent tasks per device based on thermal constraints

### RTX 4090 Optimization

- Batch processing: Increase `max_batch_size` gradually (test with 2, then 4)
- GPU memory management:
  ```python
  # In worker configuration
  "gpu": {
    "memory_limit_mb": 16384,
    "swap_system_enabled": true
  }
  ```
- Model optimization: Use smaller YOLO models for initial passes

### Storage Optimization

- Implement tiered storage:
  - Hot: Indoor NAS (recent videos)
  - Warm: Shed NAS (processed videos)
  - Cold: Object storage (archived videos >1 year old)

---

## 9. Common Workflows

### Adding a New Dashcam

1. **Register dashcam** in viofosync configuration
2. **Create ingestion task** manually if needed:
   ```bash
   curl -X POST http://main-server:8000/api/v1/tasks \
     -H "Content-Type: application/json" \
     -d '{
       "task_type": "INGEST_VIDEO",
       "video_id": "new_dashcam_video",
       "metadata": {
         "source": "dashcam-2",
         "filename": "20240101_123456.MP4"
       }
     }'
   ```

### Reprocessing a Video

1. **Find original task chain**:
   ```bash
   curl "http://main-server:8000/api/v1/tasks?video_id=VIDEO_ID&state=complete" | python -m json.tool
   ```

2. **Mark final task as pending** to restart pipeline:
   ```bash
   # Update database directly (use with caution)
   sqlite3 tasks.db "UPDATE tasks SET state='pending' WHERE task_id=12345;"
   ```

### Manual Task Creation

```bash
# Create preprocessing task
curl -X POST http://main-server:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "PREPROCESS_VIDEO",
    "video_id": "manual_video_001",
    "inputs": [{"device": "indoor_nas", "path": "/videos/raw/20240101/"}],
    "metadata": {
      "priority": "high",
      "notes": "Manual creation for testing"
    }
  }'
```

---

## 10. Logging and Debugging

### Log Locations

| Device Type | Log File Location |
|-------------|-------------------|
| Main Server | `/var/log/dashcam/server.log` |
| Jetson | `/tmp/jetson_worker.log` or `~/dashcam/workers.log` |
| RTX 4090 | Windows Event Log + `worker.log` in working directory |
| Indoor NAS | `/var/log/viofosync.log`, `/var/log/samba/log.smbd` |

### Debugging Techniques

1. **Enable verbose logging**:
   ```bash
   python -v workers/jetson_coral_worker.py --log-level DEBUG
   ```

2. **Trace task execution**:
   ```bash
   # Add to worker code temporarily
   import logging
   logging.getLogger().setLevel(logging.DEBUG)
   ```

3. **Inspect task state**:
   ```python
   from services.task_manager import TaskManager
   from sqlalchemy import create_engine
   from sqlalchemy.orm import sessionmaker

   engine = create_engine("sqlite:///tasks.db")
   SessionLocal = sessionmaker(bind=engine)
   db = SessionLocal()

   manager = TaskManager(db)
   task = manager.get_task_by_id(12345)
   print(task.to_dict())
   ```

---

## 11. Best Practices

### Configuration Management
- Use version control for configuration files
- Document all changes in config files with comments
- Test configuration changes on staging before production

### Capacity Planning
- Monitor task completion rates to predict hardware needs
- Plan for seasonal variations (holiday travel = more videos)
- Allocate storage based on: 80% raw videos, 15% intermediates, 5% buffer

### Worker Management
- Distribute workload evenly across devices of same type
- Prioritize critical tasks (flag with metadata)
- Implement graceful degradation during peak loads

---

## 12. Contact and Support

For operational issues:
- **Primary Contact**: operations@yourcompany.com
- **Escalation Path**:
  - Tier 1: System administrators (check monitoring alerts)
  - Tier 2: DevOps team (troubleshoot specific devices)
  - Tier 3: Development team (code-level issues)

Emergency procedures are documented in section 7. For immediate assistance during business hours, call [support number].