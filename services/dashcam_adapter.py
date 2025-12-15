"""Dashcam Adapter - For raw video capture ingestion."""

from typing import List, Dict, Any, Optional
import logging
import requests
import time

from .device_adapter import DeviceAdapter

logger = logging.getLogger(__name__)

class DashcamAdapter(DeviceAdapter):
    """Device adapter for dashcam video ingestion."""

    def _get_device_type(self) -> str:
        return "dashcam"

    def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Pull pending INGEST_VIDEO tasks."""
        if task_type is None:
            task_type = "INGEST_VIDEO"

        try:
            response = requests.get(
                f"{self.config['server_url']}/api/tasks",
                params={
                    "task_type": task_type,
                    "limit": limit
                },
                timeout=10
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return []
            else:
                logger.error(f"Failed to get tasks: HTTP {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"Error fetching tasks from server: {e}")
            return []

    def mark_task_complete(
        self,
        task_id: int,
        new_tasks: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Mark ingestion task as complete."""
        try:
            payload = {"task_id": task_id}

            if new_tasks:
                payload["new_tasks"] = new_tasks

            response = requests.post(
                f"{self.config['server_url']}/api/tasks/complete",
                json=payload,
                timeout=10
            )

            return response.status_code == 200

        except requests.RequestException as e:
            logger.error(f"Error marking task complete: {e}")
            return False

    def get_device_capabilities(self) -> Dict[str, Any]:
        """Return dashcam hardware capabilities."""
        return {
            "storage_type": self.config.get("storage_type", "sd_card"),
            "max_storage_gb": self.config.get("max_storage_gb", 128),
            "video_resolution": self.config.get("video_resolution", "1920x1080"),
            "frame_rate": self.config.get("frame_rate", 30),
            "gps_enabled": self.config.get("gps_enabled", True),
            "wifi_available": self.config.get("wifi_available", True)
        }

    def health_check(self) -> bool:
        """Verify dashcam is operational."""
        try:
            # Check SD card space
            if not self._check_storage_space():
                return False

            # Check battery level if applicable
            if "battery_level" in self.config and self.config["battery_level"] < 10:
                logger.warning(f"Low battery: {self.config['battery_level']}%")
                return False

            # Check WiFi connectivity
            if self.config.get("wifi_available", True):
                try:
                    requests.get(self.config["server_url"], timeout=2)
                except requests.RequestException:
                    logger.warning("WiFi connection to server failed")
                    return False

            return True

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False

    def _check_storage_space(self) -> bool:
        """Check if there's enough storage space."""
        available_gb = self.config.get("available_storage_gb", 0)
        min_required_gb = self.config.get("min_storage_threshold_gb", 5)

        if available_gb < min_required_gb:
            logger.warning(
                f"Insufficient storage: {available_gb}GB "
                f"(requires {min_required_gb}GB)"
            )
            return False

        return True

    def _execute_task(self, task: Dict[str, Any]) -> bool:
        """Ingest video from dashcam to server."""
        try:
            # Extract video file information
            inputs = task.get("inputs", [])
            if not inputs:
                logger.error(f"No input files specified for task {task['task_id']}")
                return False

            video_file = inputs[0]
            local_path = video_file["path"]

            # Transfer video to server/NAS
            transfer_success = self._transfer_video_to_server(local_path, task)

            if not transfer_success:
                logger.error(f"Video transfer failed for task {task['task_id']}")
                return False

            logger.info(
                f"Successfully ingested video from dashcam: "
                f"{video_file['path']}"
            )
            return True

        except Exception as e:
            logger.error(f"Error executing ingestion task: {e}")
            return False

    def _transfer_video_to_server(self, local_path: str, task: Dict[str, Any]) -> bool:
        """Transfer video file to server/NAS."""
        try:
            # For actual implementation, this would use SMB/NFS or HTTP upload
            # Here we simulate the transfer by marking it as complete

            # Check if file exists (simulated)
            time.sleep(1)  # Simulate transfer time

            logger.info(
                f"Transferring {local_path} to server "
                f"(task: {task['task_id']})"
            )

            return True

        except Exception as e:
            logger.error(f"Video transfer failed: {e}")
            return False

    def _get_downstream_tasks(
        self,
        completed_task: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Create PREPROCESS_VIDEO task after ingestion completes."""
        # After ingesting video, create a preprocessing task
        new_tasks = [{
            "task_type": "PREPROCESS_VIDEO",
            "video_id": completed_task.get("video_id"),
            "inputs": completed_task.get("outputs", []),
            "metadata": {
                "source": "dashcam_ingestion",
                "priority": "normal"
            },
            "device_capabilities_required": {
                "coral_tpu_available": True,
                "min_memory_gb": 4
            }
        }]

        return new_tasks