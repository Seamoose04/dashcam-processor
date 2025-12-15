"""Indoor NAS Adapter - For video file storage and retrieval."""

from typing import List, Dict, Any, Optional
import logging
import requests
import os
import time

from .device_adapter import DeviceAdapter

logger = logging.getLogger(__name__)

class IndoorNASAdapter(DeviceAdapter):
    """Device adapter for indoor NAS storage operations."""

    def _get_device_type(self) -> str:
        return "indoor_nas"

    def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Pull pending tasks (INGEST_VIDEO or ARCHIVE_VIDEO)."""
        if task_type is None:
            # Indoor NAS handles both ingestion and archival tasks
            task_types = ["INGEST_VIDEO", "ARCHIVE_VIDEO"]
        else:
            task_types = [task_type]

        all_tasks = []
        for ttype in task_types:
            try:
                response = requests.get(
                    f"{self.config['server_url']}/api/tasks",
                    params={
                        "task_type": ttype,
                        "limit": limit
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    all_tasks.extend(response.json())
                elif response.status_code != 404:
                    logger.error(f"Failed to get tasks: HTTP {response.status_code}")

            except requests.RequestException as e:
                logger.error(f"Error fetching tasks from server: {e}")
                continue

        # Return only unique tasks
        seen = set()
        unique_tasks = []
        for task in all_tasks:
            if task['task_id'] not in seen:
                seen.add(task['task_id'])
                unique_tasks.append(task)

        return unique_tasks[:limit]

    def mark_task_complete(
        self,
        task_id: int,
        new_tasks: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Mark task as complete."""
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
        """Return indoor NAS hardware capabilities."""
        return {
            "read_throughput_mbps": self.config.get("read_throughput_mbps", 100),
            "write_throughput_mbps": self.config.get("write_throughput_mbps", 50),
            "total_storage_tb": self.config.get("total_storage_tb", 8),
            "available_storage_tb": self.config.get("available_storage_tb", 4),
            "smb_available": self.config.get("smb_available", True),
            "nfs_available": self.config.get("nfs_available", False)
        }

    def health_check(self) -> bool:
        """Verify NAS is operational."""
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
        min_required_tb = self.config.get("min_storage_threshold_tb", 1)

        if available_tb < min_required_tb:
            logger.warning(
                f"Insufficient storage: {available_tb}TB "
                f"(requires {min_required_tb}TB)"
            )
            return False

        return True

    def _execute_task(self, task: Dict[str, Any]) -> bool:
        """Execute NAS task (ingestion or archival)."""
        try:
            if task["task_type"] == "INGEST_VIDEO":
                return self._handle_ingest_video(task)
            elif task["task_type"] == "ARCHIVE_VIDEO":
                return self._handle_archive_video(task)
            else:
                logger.error(f"Unknown task type: {task['task_type']}")
                return False

        except Exception as e:
            logger.error(f"Error executing NAS task: {e}")
            return False

    def _handle_ingest_video(self, task: Dict[str, Any]) -> bool:
        """Handle video ingestion from dashcam."""
        try:
            # Extract task details
            inputs = task.get("inputs", [])
            if not inputs:
                logger.error(f"No input files specified for task {task['task_id']}")
                return False

            video_file = inputs[0]
            source_path = video_file["path"]

            # Determine destination path on NAS
            dest_base = self.config["storage_paths"]["indoor_nas"]["raw"]
            video_name = os.path.basename(source_path)
            dest_path = os.path.join(dest_base, video_name)

            logger.info(
                f"Ingesting video: {source_path} -> {dest_path}"
            )

            # Simulate file transfer (actual implementation would use SMB/NFS)
            import time
            time.sleep(0.5)  # Simulate transfer

            # Update task outputs with NAS location
            self._update_task_outputs(task, dest_path)

            logger.info(f"Successfully ingested video to NAS: {dest_path}")
            return True

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            return False

    def _handle_archive_video(self, task: Dict[str, Any]) -> bool:
        """Handle video archival from heavy processing."""
        try:
            # Extract task details
            inputs = task.get("inputs", [])
            if not inputs:
                logger.error(f"No input files specified for task {task['task_id']}")
                return False

            processed_files = inputs
            dest_base = self.config["storage_paths"]["indoor_nas"]["heavy_output"]

            logger.info(
                f"Archiving {len(processed_files)} files to NAS"
            )

            # Simulate file transfer (actual implementation would use SMB/NFS)
            import time
            time.sleep(1.0)  # Simulate transfer

            # Update task outputs with NAS location
            output_paths = []
            for pf in processed_files:
                video_name = os.path.basename(pf["path"])
                dest_path = os.path.join(dest_base, video_name)
                output_paths.append({
                    "device": "indoor_nas",
                    "path": dest_path,
                    "type": pf.get("type", "processed_video")
                })

            self._update_task_outputs(task, output_paths)

            logger.info(f"Successfully archived files to NAS")
            return True

        except Exception as e:
            logger.error(f"Archival failed: {e}")
            return False

    def _update_task_outputs(
        self,
        task: Dict[str, Any],
        outputs: Any
    ) -> None:
        """Update task with output paths."""
        if isinstance(outputs, str):
            # Single file
            task["outputs"] = [{
                "device": "indoor_nas",
                "path": outputs,
                "type": "video_file"
            }]
        elif isinstance(outputs, list):
            # Multiple files
            task["outputs"] = outputs

    def _get_downstream_tasks(
        self,
        completed_task: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Create downstream tasks after NAS operations."""
        if completed_task["task_type"] == "INGEST_VIDEO":
            # After ingestion, create preprocessing task
            return [{
                "task_type": "PREPROCESS_VIDEO",
                "video_id": completed_task.get("video_id"),
                "inputs": completed_task.get("outputs", []),
                "metadata": {
                    "source": "indoor_nas_ingestion",
                    "priority": "normal"
                },
                "device_capabilities_required": {
                    "coral_tpu_available": True,
                    "min_memory_gb": 4
                }
            }]
        elif completed_task["task_type"] == "ARCHIVE_VIDEO":
            # After archival, create finalization task (if needed)
            return [{
                "task_type": "FINALIZE_VIDEO",
                "video_id": completed_task.get("video_id"),
                "inputs": completed_task.get("outputs", []),
                "metadata": {
                    "source": "indoor_nas_archival",
                    "priority": "low"
                }
            }]

        return None