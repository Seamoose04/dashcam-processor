"""Shed NAS Adapter - For final archival storage."""

from typing import List, Dict, Any, Optional
import logging
import requests
import os
import time

from .device_adapter import DeviceAdapter

logger = logging.getLogger(__name__)

class ShedNASAdapter(DeviceAdapter):
    """Device adapter for shed NAS archival operations."""

    def _get_device_type(self) -> str:
        return "shed_nas"

    def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Pull pending ARCHIVE_VIDEO tasks."""
        if task_type is None:
            task_type = "ARCHIVE_VIDEO"

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
        """Mark archival task as complete."""
        try:
            payload = {"task_id": task_id}

            if new_tasks:
                payload["new_tasks"] = [nt for nt in new_tasks]

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
        """Return shed NAS hardware capabilities."""
        return {
            "total_storage_tb": self.config.get("total_storage_tb", 24),
            "available_storage_tb": self.config.get("available_storage_tb", 16),
            "read_throughput_mbps": self.config.get("read_throughput_mbps", 100),
            "write_throughput_mbps": self.config.get("write_throughput_mbps", 50),
            "http_server_available": self.config.get("http_server_available", True)
        }

    def health_check(self) -> bool:
        """Verify shed NAS is operational."""
        try:
            # Check storage space
            if not self._check_storage_space():
                return False

            # Check network connectivity to server
            try:
                requests.get(self.config["server_url"], timeout=2)
            except requests.RequestException:
                logger.warning("Network connection to server failed")
                return False

            # Check mount points
            for mount_point in self.config.get("mount_points", []):
                if not os.path.ismount(mount_point):
                    logger.error(f"Mount point not available: {mount_point}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False

    def _check_storage_space(self) -> bool:
        """Check if there's enough storage space."""
        available_tb = self.config.get("available_storage_tb", 0)
        min_required_tb = self.config.get("min_storage_threshold_tb", 5)

        if available_tb < min_required_tb:
            logger.warning(
                f"Insufficient storage: {available_tb}TB "
                f"(requires {min_required_tb}TB)"
            )
            return False

        return True

    def _execute_task(self, task: Dict[str, Any]) -> bool:
        """Execute archival task."""
        try:
            # Extract task details
            inputs = task.get("inputs", [])
            if not inputs:
                logger.error(f"No input files specified for task {task['task_id']}")
                return False

            processed_files = inputs
            video_file = processed_files[0] if processed_files else None

            if not video_file:
                logger.error(f"No processed files specified for task {task['task_id']}")
                return False

            source_path = video_file["path"]

            logger.info(
                f"Archiving processed files: {source_path} "
                f"(task: {task['task_id']})"
            )

            # Simulate archival steps
            success = self._run_archival_pipeline(processed_files)

            if not success:
                logger.error(f"Archival failed for task {task['task_id']}")
                return False

            logger.info(
                f"Successfully completed archival: {source_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Error executing archival task: {e}")
            return False

    def _run_archival_pipeline(self, input_files: List[Dict[str, Any]]) -> bool:
        """Run the complete archival pipeline."""
        try:
            # Step 1: Transfer de-resolved videos
            logger.info("Transferring low-res videos...")
            time.sleep(2.0)

            # Step 2: Transfer high-resolution plate crops
            logger.info("Transferring plate crops...")
            time.sleep(3.0)

            # Step 3: Transfer best-frame thumbnails
            logger.info("Transferring thumbnails...")
            time.sleep(1.0)

            # Step 4: Organize by video ID and timestamp
            logger.info("Organizing archival structure...")
            time.sleep(0.5)

            return True

        except Exception as e:
            logger.error(f"Archival pipeline failed: {e}")
            return False

    def _get_downstream_tasks(
        self,
        completed_task: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Create finalization task after archival completes."""
        # After archival, the video is complete
        # No downstream tasks needed (final stage)
        return None

    def _apply_retention_policy(self, video_id: str) -> bool:
        """Apply retention policy to clean up old videos."""
        try:
            # Check if video should be retained based on age
            # Actual implementation would query video metadata from server

            logger.info(
                f"Checking retention policy for video {video_id}"
            )

            # Simulate retention check
            import time
            time.sleep(0.5)

            return True

        except Exception as e:
            logger.error(f"Retention policy check failed: {e}")
            return False