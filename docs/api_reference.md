# Dashcam Processor System - API Reference

This document provides comprehensive reference for all REST API endpoints in the dashcam processor system.

---

## 1. Overview

The API follows REST conventions and uses JSON for request/response bodies. All endpoints are prefixed with `/api/v1`.

### Base URL
```
http://{server-host}:8000/api/v1/
```

### Authentication
Currently, the API does not require authentication (for development). In production, use JWT tokens:
```bash
Authorization: Bearer {token}
```

---

## 2. Endpoints

### 2.1 Task Management Endpoints

#### `GET /tasks`
List all tasks with optional filtering.

**Parameters:**
- `task_type` (query): Filter by task type (e.g., `INGEST_VIDEO`)
- `state` (query): Filter by state (`pending` or `complete`)
- `limit` (query): Maximum number of tasks to return (default: 100, max: 1000)
- `offset` (query): Pagination offset (default: 0)

**Response:**
```json
[
  {
    "task_id": 1,
    "task_type": "INGEST_VIDEO",
    "state": "pending",
    "created_at": "2024-01-15T10:30:00",
    "completed_at": null,
    "video_id": "trip_20240115_1",
    "inputs": [{"device": "dashcam", "path": "/videos/raw/video.mp4"}],
    "outputs": [],
    "metadata": {"source": "dashcam-1"},
    "device_capabilities_required": {}
  }
]
```

**Example Request:**
```bash
curl "http://main-server:8000/api/v1/tasks?state=pending&limit=50"
```

---

#### `GET /tasks/{task_id}`
Get a specific task by ID.

**Response:**
```json
{
  "task_id": 1,
  "task_type": "INGEST_VIDEO",
  "state": "pending",
  "created_at": "2024-01-15T10:30:00",
  "completed_at": null,
  "video_id": "trip_20240115_1",
  "inputs": [{"device": "dashcam", "path": "/videos/raw/video.mp4"}],
  "outputs": [],
  "metadata": {"source": "dashcam-1"},
  "device_capabilities_required": {}
}
```

**Example Request:**
```bash
curl "http://main-server:8000/api/v1/tasks/1"
```

---

#### `POST /tasks`
Create a new task.

**Request Body:**
```json
{
  "task_type": "PREPROCESS_VIDEO",
  "video_id": "trip_20240115_1",
  "inputs": [{"device": "indoor_nas", "path": "/videos/raw/video.mp4"}],
  "metadata": {"priority": "normal"},
  "device_capabilities_required": {
    "gpu_vram_gb": 8
  }
}
```

**Required Fields:**
- `task_type` (string): One of `INGEST_VIDEO`, `PREPROCESS_VIDEO`, `HEAVY_PROCESS_VIDEO`, `ARCHIVE_VIDEO`

**Response:**
```json
{
  "task_id": 2,
  "task_type": "PREPROCESS_VIDEO",
  "state": "pending",
  "created_at": "2024-01-15T10:35:00",
  "completed_at": null,
  "video_id": "trip_20240115_1",
  "inputs": [{"device": "indoor_nas", "path": "/videos/raw/video.mp4"}],
  "outputs": [],
  "metadata": {"priority": "normal"},
  "device_capabilities_required": {"gpu_vram_gb": 8}
}
```

**Example Request:**
```bash
curl -X POST "http://main-server:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "PREPROCESS_VIDEO",
    "video_id": "trip_20240115_1"
  }'
```

---

#### `POST /tasks/{task_id}/complete`
Mark a task as complete and optionally publish new downstream tasks.

**Request Body:**
```json
{
  "new_tasks": [
    {
      "task_type": "HEAVY_PROCESS_VIDEO",
      "video_id": "trip_20240115_1",
      "inputs": [{"device": "jetson_coral", "path": "/preproc/trip_20240115_1/"}]
    }
  ]
}
```

**Response:**
```json
{
  "message": "Task 1 marked as complete",
  "task_type": "INGEST_VIDEO",
  "completed_at": "2024-01-15T10:36:00",
  "new_tasks_created": 1
}
```

**Example Request:**
```bash
curl -X POST "http://main-server:8000/api/v1/tasks/1/complete" \
  -H "Content-Type: application/json" \
  -d '{
    "new_tasks": [{
      "task_type": "PREPROCESS_VIDEO",
      "video_id": "trip_20240115_1"
    }]
  }'
```

---

#### `GET /tasks/pending`
Get pending tasks for pull-based execution (main worker endpoint).

**Parameters:**
- `task_type` (query): Filter by specific task type
- `limit` (query): Maximum number of tasks to return (default: 1, max: 100)
- `device_capabilities` (body): Device capabilities for filtering

**Request Body (for device capabilities):**
```json
{
  "gpu_vram_gb": 16,
  "cpu_cores": 8,
  "storage_gb": 500
}
```

**Response:**
```json
[
  {
    "task_id": 2,
    "task_type": "PREPROCESS_VIDEO",
    "state": "pending",
    "created_at": "2024-01-15T10:35:00",
    "completed_at": null,
    "video_id": "trip_20240115_1",
    "inputs": [{"device": "indoor_nas", "path": "/videos/raw/video.mp4"}],
    "outputs": [],
    "metadata": {},
    "device_capabilities_required": {}
  }
]
```

**Example Request:**
```bash
curl -X GET "http://main-server:8000/api/v1/tasks/pending?task_type=PREPROCESS_VIDEO" \
  -H "Content-Type: application/json" \
  -d '{"gpu_vram_gb": 8}'
```

---

### 2.2 Device Management Endpoints

#### `GET /devices`
List all registered devices.

**Response:**
```json
[
  {
    "device_id": 1,
    "hostname": "jetson-coral-1",
    "device_type": "jetson_coral",
    "status": "online",
    "last_heartbeat": "2024-01-15T10:30:00",
    "tasks_running": 0,
    "capabilities": {
      "gpu_vram_gb": 8,
      "cpu_cores": 4,
      "storage_gb": 32
    }
  }
]
```

**Example Request:**
```bash
curl "http://main-server:8000/api/v1/devices"
```

---

#### `GET /devices/{hostname}`
Get specific device by hostname.

**Response:**
```json
{
  "device_id": 1,
  "hostname": "jetson-coral-1",
  "device_type": "jetson_coral",
  "status": "online",
  "last_heartbeat": "2024-01-15T10:30:00",
  "tasks_running": 0,
  "capabilities": {
    "gpu_vram_gb": 8,
    "cpu_cores": 4,
    "storage_gb": 32
  }
}
```

**Example Request:**
```bash
curl "http://main-server:8000/api/v1/devices/jetson-coral-1"
```

---

#### `POST /devices/heartbeat`
Update device heartbeat and status.

**Request Body:**
```json
{
  "hostname": "jetson-coral-1",
  "device_type": "jetson_coral",
  "status": "online",
  "capabilities": {
    "gpu_vram_gb": 8,
    "cpu_cores": 4,
    "storage_gb": 32
  }
}
```

**Required Fields:**
- `hostname` (string): Device hostname
- `device_type` (string): Type of device

**Response:**
```json
{
  "message": "Heartbeat received for jetson-coral-1",
  "device_id": 1,
  "last_heartbeat": "2024-01-15T10:36:00"
}
```

**Example Request:**
```bash
curl -X POST "http://main-server:8000/api/v1/devices/heartbeat" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "jetson-coral-1",
    "device_type": "jetson_coral"
  }'
```

---

### 2.3 WebUI Endpoints

#### `GET /webui/videos`
List all processed videos for WebUI display.

**Parameters:**
- `limit` (query): Maximum number of videos (default: 50)
- `offset` (query): Pagination offset
- `date_from` (query): Filter by start date (YYYY-MM-DD)
- `date_to` (query): Filter by end date (YYYY-MM-DD)

**Response:**
```json
[
  {
    "video_id": "trip_20240115_1",
    "filename": "20240115_123456.MP4",
    "date_recorded": "2024-01-15",
    "duration_seconds": 1800,
    "total_frames": 1500,
    "detections_count": 42,
    "plates_found": 12,
    "status": "processed",
    "archive_path": "//shed-nas/archive/trip_20240115_1/"
  }
]
```

**Example Request:**
```bash
curl "http://main-server:8000/api/v1/webui/videos?date_from=2024-01-15&limit=20"
```

---

#### `GET /webui/videos/{video_id}`
Get detailed information about a specific video.

**Response:**
```json
{
  "video_id": "trip_20240115_1",
  "filename": "20240115_123456.MP4",
  "date_recorded": "2024-01-15T12:34:56",
  "duration_seconds": 1800,
  "total_frames": 1500,
  "detections_count": 42,
  "plates_found": 12,
  "status": "processed",
  "archive_path": "//shed-nas/archive/trip_20240115_1/",
  "gps_route": [
    {"lat": 37.7749, "lon": -122.4194, "timestamp": "2024-01-15T12:34:56"},
    {"lat": 37.7750, "lon": -122.4195, "timestamp": "2024-01-15T12:35:00"}
  ],
  "timeline": {
    "plates": [
      {"frame": 120, "plate": "ABC123", "confidence": 0.92},
      {"frame": 456, "plate": "XYZ789", "confidence": 0.88}
    ]
  }
}
```

**Example Request:**
```bash
curl "http://main-server:8000/api/v1/webui/videos/trip_20240115_1"
```

---

#### `GET /webui/plates`
Search for license plates across all videos.

**Parameters:**
- `plate_query` (query): Partial plate text to search for
- `date_from` (query): Filter by start date
- `date_to` (query): Filter by end date

**Response:**
```json
[
  {
    "video_id": "trip_20240115_1",
    "plate_text": "ABC123",
    "confidence": 0.92,
    "frame_number": 120,
    "timestamp": "2024-01-15T12:36:45",
    "location": {"lat": 37.7749, "lon": -122.4194},
    "thumbnail_url": "//shed-nas/archive/trip_20240115_1/plates/ABC123_thumb.jpg"
  }
]
```

**Example Request:**
```bash
curl "http://main-server:8000/api/v1/webui/plates?plate_query=ABC&date_from=2024-01-15"
```

---

## 3. Task Types

### `INGEST_VIDEO`
Initial ingestion of raw dashcam footage.

**Typical Flow:**
```
Dashcam → Indoor NAS (creates task) → Main Server
```

**Example Task:**
```json
{
  "task_type": "INGEST_VIDEO",
  "video_id": "trip_20240115_1",
  "inputs": [{"device": "dashcam", "path": "/sdcard/20240115_123456.MP4"}],
  "metadata": {
    "source": "dashcam-1",
    "filename": "20240115_123456.MP4"
  }
}
```

---

### `PREPROCESS_VIDEO`
Lightweight preprocessing using Jetson Coral.

**Typical Flow:**
```
Main Server → Jetson Coral → Main Server (creates HEAVY_PROCESS_VIDEO)
```

**Example Task:**
```json
{
  "task_type": "PREPROCESS_VIDEO",
  "video_id": "trip_20240115_1",
  "inputs": [{"device": "indoor_nas", "path": "/videos/raw/20240115_123456.MP4"}],
  "outputs": [
    {"device": "indoor_nas", "path": "/videos/preproc/trip_20240115_1/metadata.json"},
    {"device": "indoor_nas", "path": "/videos/preproc/trip_20240115_1/thumbs/"}
  ],
  "metadata": {
    "frame_count": 1500,
    "filtered_frames": 300
  }
}
```

---

### `HEAVY_PROCESS_VIDEO`
Full-resolution GPU processing using RTX 4090.

**Typical Flow:**
```
Main Server → RTX 4090 → Main Server (creates ARCHIVE_VIDEO)
```

**Example Task:**
```json
{
  "task_type": "HEAVY_PROCESS_VIDEO",
  "video_id": "trip_20240115_1",
  "inputs": [
    {"device": "indoor_nas", "path": "/videos/raw/20240115_123456.MP4"},
    {"device": "indoor_nas", "path": "/videos/preproc/trip_20240115_1/"}
  ],
  "outputs": [
    {"device": "rtx_4090", "path": "/temp/detections/trip_20240115_1.json"},
    {"device": "indoor_nas", "path": "/videos/heavy_output/trip_20240115_1/"}
  ],
  "metadata": {
    "detections_count": 42,
    "plates_found": 12
  },
  "device_capabilities_required": {
    "gpu_vram_gb": 8,
    "cpu_cores": 6
  }
}
```

---

### `ARCHIVE_VIDEO`
Final archival to Shed NAS.

**Typical Flow:**
```
Main Server → Shed NAS → Main Server (video marked as complete)
```

**Example Task:**
```json
{
  "task_type": "ARCHIVE_VIDEO",
  "video_id": "trip_20240115_1",
  "inputs": [
    {"device": "indoor_nas", "path": "/videos/heavy_output/trip_20240115_1/"},
    {"device": "rtx_4090", "path": "/temp/crops/trip_20240115_1/"}
  ],
  "outputs": [
    {"device": "shed_nas", "path": "//shed-nas/archive/trip_20240115_1/video_lowres.mp4"},
    {"device": "shed_nas", "path": "//shed-nas/archive/trip_20240115_1/plates/"}
  ],
  "metadata": {
    "finalized": true,
    "archive_size_mb": 450
  }
}
```

---

## 4. Input/Output File References

File references in tasks use this structure:

```json
{
  "device": "indoor_nas",
  "path": "/videos/raw/video.mp4",
  "type": "video",
  "temporary": false
}
```

**Fields:**
- `device` (string, required): Device where file is located
- `path` (string, required): Path to the file
- `type` (string, optional): File type (`video`, `image`, `json`, etc.)
- `temporary` (boolean, optional): Whether file can be deleted after processing

---

## 5. Device Capabilities

Devices can advertise their capabilities in heartbeats:

```json
{
  "gpu_vram_gb": 16,
  "cpu_cores": 8,
  "storage_gb": 500,
  "has_coral_tpu": true,
  "network_bandwidth_mbps": 1000
}
```

Tasks can require specific capabilities:

```json
{
  "device_capabilities_required": {
    "gpu_vram_gb": 8,
    "cpu_cores": 6
  }
}
```

---

## 6. Error Responses

### Common HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `200 OK` | Success | Request completed successfully |
| `201 Created` | Resource created | Task was created |
| `400 Bad Request` | Invalid request | Missing required fields or validation error |
| `404 Not Found` | Resource not found | Task or device doesn't exist |
| `500 Internal Server Error` | Server error | Unexpected server-side error |

### Example Error Response

```json
{
  "detail": "Task 999 not found"
}
```

---

## 7. Rate Limiting

The API implements basic rate limiting:
- **100 requests per minute** per IP address
- **10 concurrent connections** maximum

Exceeding these limits returns `429 Too Many Requests`.

---

## 8. WebSocket Support (Future)

Planned WebSocket endpoints for real-time updates:

```javascript
// Connect to task updates
const ws = new WebSocket("ws://main-server:8000/api/v1/ws/tasks");

// Subscribe to specific video
ws.send(JSON.stringify({
  "action": "subscribe",
  "video_id": "trip_20240115_1"
}));

// Receive updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Task updated:", data);
};
```

---

## 9. API Usage Examples

### Example 1: Complete Video Processing Pipeline

```bash
#!/bin/bash
# Process a new video from ingestion to archival

# Step 1: Create ingestion task
INGESTION_TASK=$(curl -s -X POST "http://main-server:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "INGEST_VIDEO",
    "video_id": "trip_20240115_1"
  }' | python -m json.tool)

echo "Created ingestion task: $INGESTION_TASK"

# Step 2: Wait for ingestion to complete
while true; do
  STATE=$(curl -s "http://main-server:8000/api/v1/tasks/$(echo $INGESTION_TASK | jq -r '.task_id')" | jq -r '.state')
  if [ "$STATE" = "complete" ]; then
    break
  fi
  sleep 5
done

# Step 3: Create preprocessing task (would normally be done by server)
PREPROC_TASK=$(curl -s -X POST "http://main-server:8000/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "PREPROCESS_VIDEO",
    "video_id": "trip_20240115_1"
  }' | python -m json.tool)

echo "Created preprocessing task: $PREPROC_TASK"

# Step 4: Mark preprocessing complete and create heavy processing task
curl -s -X POST "http://main-server:8000/api/v1/tasks/$(echo $PREPROC_TASK | jq -r '.task_id')/complete" \
  -H "Content-Type: application/json" \
  -d '{
    "new_tasks": [{
      "task_type": "HEAVY_PROCESS_VIDEO",
      "video_id": "trip_20240115_1"
    }]
  }'

echo "Pipeline started successfully!"
```

---

### Example 2: Query Processing Statistics

```python
import requests
import json
from datetime import datetime, timedelta

def get_processing_stats():
    base_url = "http://main-server:8000/api/v1"

    # Get all completed tasks from last week
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    tasks = requests.get(f"{base_url}/tasks?state=complete").json()

    stats = {
        "total_videos": 0,
        "total_processing_time": 0,
        "tasks_by_type": {},
        "devices_active": set()
    }

    for task in tasks:
        task_type = task["task_type"]
        stats["tasks_by_type"][task_type] = stats["tasks_by_type"].get(task_type, 0) + 1

        if task.get("completed_at"):
            created = datetime.fromisoformat(task["created_at"])
            completed = datetime.fromisoformat(task["completed_at"])
            processing_time = (completed - created).total_seconds()
            stats["total_processing_time"] += processing_time

        if "video_id" in task:
            stats["total_videos"] = len(set([t["video_id"] for t in tasks]))

    # Get device information
    devices = requests.get(f"{base_url}/devices").json()
    for device in devices:
        stats["devices_active"].add(device["hostname"])

    return stats

if __name__ == "__main__":
    stats = get_processing_stats()
    print(json.dumps(stats, indent=2))
```

---

### Example 3: Bulk Task Creation

```bash
#!/bin/bash
# Create tasks for multiple videos from a CSV file

CSV_FILE="videos_to_process.csv"

while IFS=, read -r video_id filename source; do
  echo "Creating task for $video_id ($filename) from $source"

  curl -s -X POST "http://main-server:8000/api/v1/tasks" \
    -H "Content-Type: application/json" \
    -d "{
      \"task_type\": \"INGEST_VIDEO\",
      \"video_id\": \"$video_id\",
      \"metadata\": {
        \"source\": \"$source\",
        \"filename\": \"$filename\"
      }
    }" > /dev/null

  echo "Created task for $video_id"
done < "$CSV_FILE"

echo "All tasks created successfully!"
```

---

## 10. API Versioning

The current API version is `v1`. Future versions will be introduced as:
- `/api/v2/...` for new major versions
- Backward compatibility will be maintained where possible
- Deprecation warnings will be provided before breaking changes

---

## 11. OpenAPI/Swagger Documentation

Interactive API documentation is available at:
```
http://main-server:8000/docs
http://main-server:8000/redoc
```

These endpoints provide:
- Interactive request building
- Response schema examples
- Authentication testing
- Endpoint descriptions and parameters

---

## 12. Best Practices for API Usage

### Client-Side Considerations

1. **Implement retry logic** for transient failures (5xx errors)
2. **Use exponential backoff** when rate-limited:
   ```python
   import time
   import requests

   def make_request_with_retry(url, max_retries=3):
       for attempt in range(max_retries):
           try:
               response = requests.get(url)
               if response.status_code == 429 and attempt < max_retries - 1:
                   sleep_time = (2 ** attempt) + random.uniform(0, 1)
                   time.sleep(sleep_time)
                   continue
               return response
           except requests.RequestException as e:
               if attempt == max_retries - 1:
                   raise
               time.sleep(1)
   ```

3. **Cache responses** where appropriate (especially for device listings)

### Server-Side Considerations

1. **Monitor API usage** to detect anomalies
2. **Log all failed requests** with details
3. **Implement circuit breakers** for dependent services

---

## 13. Troubleshooting API Issues

### Common Problems

| Problem | Symptoms | Solution |
|---------|----------|----------|
| Connection refused | `curl: (7) Failed to connect` | Check if server is running (`systemctl status dashcam-server`) |
| Authentication failed | `401 Unauthorized` | Verify JWT token or API key |
| Rate limited | `429 Too Many Requests` | Implement retry with backoff |
| Invalid JSON | `400 Bad Request` | Validate request body format |

### Debugging Tips

1. **Check server logs**:
   ```bash
   tail -f /var/log/dashcam/server.log
   ```

2. **Test connectivity**:
   ```bash
   curl -v http://main-server:8000/api/v1/tasks
   ```

3. **Validate request format**:
   ```python
   import json
   from config.loader import ConfigurationLoader

   # Validate task structure
   try:
       task_data = json.loads(request_body)
       loader = ConfigurationLoader()
       errors = loader.validate_config(task_data)
       if errors:
           raise ValueError("\n".join(errors))
   except Exception as e:
       return {"error": str(e)}, 400
   ```

---

## 14. API Monitoring

### Key Metrics to Track

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Request rate | Requests per minute | >1000 req/min |
| Error rate | Percentage of 5xx errors | >5% |
| Latency (p95) | Response time for successful requests | >2 seconds |
| Active connections | Current WebSocket/API connections | >100 |
| Task creation rate | New tasks created per minute | N/A |

### Monitoring Endpoint

```bash
# Get basic metrics
curl "http://main-server:8000/api/v1/metrics"

# Response includes:
# - Request count by endpoint
# - Error count by status code
# - Average response times
```

---

## 15. Migration Guide for API Changes

### Breaking Changes in v2 (Planned)

1. **Authentication**: Will require JWT tokens
   ```bash
   # Current (no auth)
   curl http://main-server:8000/api/v1/tasks

   # Future (with auth)
   curl -H "Authorization: Bearer $TOKEN" http://main-server:8000/api/v2/tasks
   ```

2. **Task filtering**: New query parameters
   ```bash
   # Current
   curl "http://main-server:8000/api/v1/tasks?state=pending&limit=50"

   # Future (more flexible)
   curl "http://main-server:8000/api/v2/tasks?filter[state]=pending&page[limit]=50"
   ```

3. **Pagination**: Standardized format
   ```json
   {
     "data": [...],
     "meta": {
       "total": 100,
       "pages": 5,
       "current_page": 1
     }
   }
   ```

---

## 16. Reference Tables

### HTTP Methods and Usage

| Method | Usage |
|--------|-------|
| `GET` | Retrieve resources (read-only) |
| `POST` | Create new resources or actions |
| `PUT` | Replace entire resource (rarely used) |
| `PATCH` | Partial updates to resources |
| `DELETE` | Remove resources |

### Content Types

| Type | Usage |
|------|-------|
| `application/json` | Primary content type for all endpoints |
| `application/x-www-form-urlencoded` | Alternative for simple data (not recommended) |
| `multipart/form-data` | For file uploads (not currently used) |

### Response Headers

| Header | Description |
|--------|-------------|
| `Content-Type: application/json` | Always present in responses |
| `X-RateLimit-Limit` | Request limit per minute |
| `X-RateLimit-Remaining` | Remaining requests |
| `X-RateLimit-Reset` | Time when limit resets (Unix timestamp) |

---

## 17. Complete API Workflow Example

### Scenario: Processing a New Video Through the Entire Pipeline

```bash
#!/bin/bash
set -e

SERVER="http://main-server:8000"
VIDEO_ID="trip_20240115_new"

echo "=== Starting video processing pipeline ==="

# Step 1: Create ingestion task (simulating Indoor NAS)
echo "1. Creating INGEST_VIDEO task..."
INGEST_RESPONSE=$(curl -s -X POST "$SERVER/api/v1/tasks" \
  -H "Content-Type: application/json" \
  -d "{
    \"task_type\": \"INGEST_VIDEO\",
    \"video_id\": \"$VIDEO_ID\",
    \"metadata\": {
      \"source\": \"dashcam-2\",
      \"filename\": \"20240115_new.MP4\"
    }
  }")

INGEST_TASK_ID=$(echo $INGEST_RESPONSE | jq -r '.task_id')
echo "   Created task $INGEST_TASK_ID"

# Step 2: Simulate ingestion completion (Indoor NAS marks task complete)
echo "2. Marking ingestion as complete..."
curl -s -X POST "$SERVER/api/v1/tasks/$INGEST_TASK_ID/complete" \
  -H "Content-Type: application/json" \
  -d "{
    \"new_tasks\": [{
      \"task_type\": \"PREPROCESS_VIDEO\",
      \"video_id\": \"$VIDEO_ID\"
    }]
  }" > /dev/null
echo "   Ingestion complete, created PREPROCESS_VIDEO task"

# Step 3: Get preprocessing task (Jetson pulls it)
echo "3. Jetson pulling PREPROCESS_VIDEO task..."
PREPROC_TASK=$(curl -s "$SERVER/api/v1/tasks/pending?task_type=PREPROCESS_VIDEO" \
  -H "Content-Type: application/json" \
  -d '{"gpu_vram_gb": 8}')
PREPROC_TASK_ID=$(echo $PREPROC_TASK | jq -r '.[0].task_id')
echo "   Pulled task $PREPROC_TASK_ID"

# Step 4: Simulate preprocessing completion
echo "4. Marking preprocessing as complete..."
curl -s -X POST "$SERVER/api/v1/tasks/$PREPROC_TASK_ID/complete" \
  -H "Content-Type: application/json" \
  -d "{
    \"new_tasks\": [{
      \"task_type\": \"HEAVY_PROCESS_VIDEO\",
      \"video_id\": \"$VIDEO_ID\"
    }]
  }" > /dev/null
echo "   Preprocessing complete, created HEAVY_PROCESS_VIDEO task"

# Step 5: Get heavy processing task (RTX 4090 pulls it)
echo "5. RTX 4090 pulling HEAVY_PROCESS_VIDEO task..."
HEAVY_TASK=$(curl -s "$SERVER/api/v1/tasks/pending?task_type=HEAVY_PROCESS_VIDEO" \
  -H "Content-Type: application/json" \
  -d '{"gpu_vram_gb": 16}')
HEAVY_TASK_ID=$(echo $HEAVY_TASK | jq -r '.[0].task_id')
echo "   Pulled task $HEAVY_TASK_ID"

# Step 6: Simulate heavy processing completion
echo "6. Marking heavy processing as complete..."
curl -s -X POST "$SERVER/api/v1/tasks/$HEAVY_TASK_ID/complete" \
  -H "Content-Type: application/json" \
  -d "{
    \"new_tasks\": [{
      \"task_type\": \"ARCHIVE_VIDEO\",
      \"video_id\": \"$VIDEO_ID\"
    }]
  }" > /dev/null
echo "   Heavy processing complete, created ARCHIVE_VIDEO task"

# Step 7: Get archival task (Shed NAS pulls it)
echo "7. Shed NAS pulling ARCHIVE_VIDEO task..."
ARCHIVE_TASK=$(curl -s "$SERVER/api/v1/tasks/pending?task_type=ARCHIVE_VIDEO")
ARCHIVE_TASK_ID=$(echo $ARCHIVE_TASK | jq -r '.[0].task_id')
echo "   Pulled task $ARCHIVE_TASK_ID"

# Step 8: Mark archival as complete (final step)
echo "8. Marking archival as complete..."
curl -s -X POST "$SERVER/api/v1/tasks/$ARCHIVE_TASK_ID/complete" > /dev/null
echo "   Archival complete!"

# Verification
echo ""
echo "=== Verification ==="
echo "All tasks for video $VIDEO_ID:"
curl -s "$SERVER/api/v1/tasks?video_id=$VIDEO_ID" | jq '.[] | {task_id, task_type, state}'

echo ""
echo "=== Pipeline completed successfully! ==="
```

This script demonstrates the complete workflow from ingestion to final archival.