"""Jetson Coral Adapter - For lightweight pre-processing tasks."""

from typing import List, Dict, Any, Optional
import logging
import requests
import time

from .device_adapter import DeviceAdapter

logger = logging.getLogger(__name__)

class JetsonCoralAdapter(DeviceAdapter):
    """Device adapter for Jetson Coral preprocessing operations."""

    def _get_device_type(self) -> str:
        return "jetson_coral"

    def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Pull pending PREPROCESS_VIDEO tasks."""
        if task_type is None:
            task_type = "PREPROCESS_VIDEO"

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
        """Mark preprocessing task as complete."""
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
        """Return Jetson Coral hardware capabilities."""
        return {
            "coral_tpu_available": self.config.get("coral_tpu_available", True),
            "tpu_top_s": self.config.get("tpu_top_s", 4),
            "cpu_cores": self.config.get("cpu_cores", 4),
            "ram_gb": self.config.get("ram_gb", 4),
            "scratch_space_gb": self.config.get("scratch_space_gb", 32),
            "opencv_available": self.config.get("opencv_available", True)
        }

    def health_check(self) -> bool:
        """Verify Jetson Coral is operational."""
        try:
            # Check Coral TPU
            if not self._check_coral_tpu():
                return False

            # Check scratch space
            if not self._check_scratch_space():
                return False

            # Check network connectivity to server
            try:
                requests.get(self.config["server_url"], timeout=2)
            except requests.RequestException:
                logger.warning("Network connection to server failed")
                return False

            return True

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return False

    def _check_coral_tpu(self) -> bool:
        """Check if Coral TPU is available and functioning."""
        # Simulate TPU health check
        if not self.config.get("coral_tpu_available", True):
            logger.error("Coral TPU not available")
            return False

        # Actual implementation would test TPU functionality
        time.sleep(0.1)
        return True

    def _check_scratch_space(self) -> bool:
        """Check if there's enough scratch space."""
        available_gb = self.config.get("scratch_space_gb", 0)
        min_required_gb = self.config.get("min_scratch_threshold_gb", 5)

        if available_gb < min_required_gb:
            logger.warning(
                f"Insufficient scratch space: {available_gb}GB "
                f"(requires {min_required_gb}GB)"
            )
            return False

        return True

    def _execute_task(self, task: Dict[str, Any]) -> bool:
        """Execute preprocessing task using Coral TPU."""
        try:
            # Extract task details
            inputs = task.get("inputs", [])
            if not inputs:
                logger.error(f"No input files specified for task {task['task_id']}")
                return False

            video_file = inputs[0]
            source_path = video_file["path"]

            logger.info(
                f"Preprocessing video: {source_path} "
                f"(task: {task['task_id']})"
            )

            # Simulate preprocessing steps
            success = self._run_preprocessing_pipeline(video_file)

            if not success:
                logger.error(f"Preprocessing failed for task {task['task_id']}")
                return False

            logger.info(
                f"Successfully preprocessed video: {source_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Error executing preprocessing task: {e}")
            return False

    def _run_preprocessing_pipeline(self, video_file: Dict[str, Any]) -> bool:
        """Run the complete preprocessing pipeline."""
        try:
            # Step 1: Frame extraction at reduced resolution
            logger.info("Extracting frames...")
            time.sleep(0.5)

            # Step 2: Motion filtering (80-95% frame reduction)
            logger.info("Applying motion filtering...")
            time.sleep(1.0)

            # Step 3: Coral TPU-based plate region proposals
            if self.config.get("coral_tpu_available", True):
                logger.info("Running Coral TPU inference for plate detection...")
                time.sleep(2.0)
            else:
                logger.warning("Coral TPU not available, using CPU fallback")
                time.sleep(3.0)

            # Step 4: Basic quality metrics collection
            logger.info("Collecting quality metrics...")
            time.sleep(0.5)

            return True

        except Exception as e:
            logger.error(f"Preprocessing pipeline failed: {e}")
            return False

    def _get_downstream_tasks(
        self,
        completed_task: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Create HEAVY_PROCESS_VIDEO task after preprocessing completes."""
        # Create heavy processing task with preprocessing outputs
        new_tasks = [{
            "task_type": "HEAVY_PROCESS_VIDEO",
            "video_id": completed_task.get("video_id"),
            "inputs": completed_task.get("outputs", []),
            "metadata": {
                "source": "jetson_coral_preprocessing",
                "priority": "high",
                "preproc_metadata": self._get_preproc_metadata(completed_task)
            },
            "device_capabilities_required": {
                "cuda_cores": 16384,
                "vram_gb": 24
            }
        }]

        return new_tasks

    def _get_preproc_metadata(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Extract preprocessing metadata for heavy processing."""
        return {
            "frame_count": task.get("metadata", {}).get("frame_count", 0),
            "motion_filtered_frames": task.get("metadata", {}).get(
                "motion_filtered_frames",
                0
            ),
            "plate_proposals": task.get("metadata", {}).get("plate_proposals", []),
            "quality_score": task.get("metadata", {}).get("quality_score", 0.0)
        }