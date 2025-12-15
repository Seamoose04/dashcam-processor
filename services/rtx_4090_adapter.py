"""RTX 4090 Adapter - For heavy GPU processing tasks."""

from typing import List, Dict, Any, Optional
import logging
import requests
import time

from .device_adapter import DeviceAdapter

logger = logging.getLogger(__name__)

class RTX4090Adapter(DeviceAdapter):
    """Device adapter for RTX 4090 heavy GPU processing."""

    def _get_device_type(self) -> str:
        return "rtx_4090"

    def get_pending_tasks(
        self,
        task_type: Optional[str] = None,
        limit: int = 1
    ) -> List[Dict[str, Any]]:
        """Pull pending HEAVY_PROCESS_VIDEO tasks."""
        if task_type is None:
            task_type = "HEAVY_PROCESS_VIDEO"

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
        """Mark heavy processing task as complete."""
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
        """Return RTX 4090 hardware capabilities."""
        return {
            "cuda_cores": self.config.get("cuda_cores", 16384),
            "vram_gb": self.config.get("vram_gb", 24),
            "cpu_cores": self.config.get("cpu_cores", 16),
            "scratch_space_gb": self.config.get("scratch_space_gb", 500),
            "cudnn_available": self.config.get("cudnn_available", True)
        }

    def health_check(self) -> bool:
        """Verify RTX 4090 is operational."""
        try:
            # Check GPU driver
            if not self._check_gpu_driver():
                return False

            # Check VRAM availability
            if not self._check_vram():
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

    def _check_gpu_driver(self) -> bool:
        """Check if GPU driver is available."""
        # Simulate driver check
        time.sleep(0.1)
        return self.config.get("cudnn_available", True)

    def _check_vram(self) -> bool:
        """Check if VRAM is available."""
        available_gb = self.config.get("vram_gb", 0)
        min_required_gb = self.config.get("min_vram_threshold_gb", 5)

        if available_gb < min_required_gb:
            logger.warning(
                f"Insufficient VRAM: {available_gb}GB "
                f"(requires {min_required_gb}GB)"
            )
            return False

        return True

    def _check_scratch_space(self) -> bool:
        """Check if there's enough scratch space."""
        available_gb = self.config.get("scratch_space_gb", 0)
        min_required_gb = self.config.get("min_scratch_threshold_gb", 10)

        if available_gb < min_required_gb:
            logger.warning(
                f"Insufficient scratch space: {available_gb}GB "
                f"(requires {min_required_gb}GB)"
            )
            return False

        return True

    def _execute_task(self, task: Dict[str, Any]) -> bool:
        """Execute heavy processing task using GPU."""
        try:
            # Extract task details
            inputs = task.get("inputs", [])
            if not inputs:
                logger.error(f"No input files specified for task {task['task_id']}")
                return False

            preproc_files = inputs
            video_file = preproc_files[0] if preproc_files else None

            if not video_file:
                logger.error(f"No video file specified for task {task['task_id']}")
                return False

            source_path = video_file["path"]

            logger.info(
                f"Heavy processing video: {source_path} "
                f"(task: {task['task_id']})"
            )

            # Simulate heavy processing steps
            success = self._run_heavy_processing_pipeline(preproc_files)

            if not success:
                logger.error(f"Heavy processing failed for task {task['task_id']}")
                return False

            logger.info(
                f"Successfully completed heavy processing: {source_path}"
            )
            return True

        except Exception as e:
            logger.error(f"Error executing heavy processing task: {e}")
            return False

    def _run_heavy_processing_pipeline(self, input_files: List[Dict[str, Any]]) -> bool:
        """Run the complete heavy processing pipeline."""
        try:
            # Step 1: Load preprocessed data
            logger.info("Loading preprocessed data...")
            time.sleep(0.5)

            # Step 2: Full-resolution YOLO detection using Jetson proposals
            logger.info("Running YOLO detection on GPU...")
            time.sleep(3.0)

            # Step 3: GPU-accelerated OCR with multi-frame aggregation
            logger.info("Running OCR processing...")
            time.sleep(2.5)

            # Step 4: GPS timestamp alignment and coordinate mapping
            logger.info("Aligning GPS data...")
            time.sleep(1.0)

            # Step 5: Best crop/frame selection algorithms
            logger.info("Selecting best frames...")
            time.sleep(1.5)

            return True

        except Exception as e:
            logger.error(f"Heavy processing pipeline failed: {e}")
            return False

    def _get_downstream_tasks(
        self,
        completed_task: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Create ARCHIVE_VIDEO task after heavy processing completes."""
        # Create archival task with heavy processing outputs
        new_tasks = [{
            "task_type": "ARCHIVE_VIDEO",
            "video_id": completed_task.get("video_id"),
            "inputs": completed_task.get("outputs", []),
            "metadata": {
                "source": "rtx_4090_processing",
                "priority": "normal",
                "detection_count": self._get_detection_count(completed_task)
            },
            "device_capabilities_required": {
                "storage_type": "nas"
            }
        }]

        return new_tasks

    def _get_detection_count(self, task: Dict[str, Any]) -> int:
        """Extract detection count from task metadata."""
        return task.get("metadata", {}).get("detection_count", 0)