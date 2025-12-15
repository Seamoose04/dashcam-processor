"""RTX 4090 Worker - Pulls HEAVY_PROCESS_VIDEO tasks for GPU-accelerated processing."""

import time
import logging
from typing import Dict, Any

from config.loader import ConfigurationLoader
from services.rtx_4090_adapter import RTX4090Adapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class RTX4090Worker:
    """Worker that pulls and processes HEAVY_PROCESS_VIDEO tasks using RTX 4090 GPU."""

    def __init__(self, device_id: str = "rtx-4090-1", server_url: str = "http://localhost:8000"):
        """Initialize RTX 4090 Worker.

        Args:
            device_id: Unique identifier for this GPU worker
            server_url: URL of the main server
        """
        self.device_id = device_id
        self.server_url = server_url.rstrip('/')
        self.config_loader = ConfigurationLoader()
        self.adapter = RTX4090Adapter(device_id, config=self.config_loader.get_device_config(device_id))
        self.running = False

    def start(self) -> None:
        """Start the worker loop."""
        logger.info(f"Starting {self.device_id} rtx 4090 worker")
        self.running = True

        while self.running:
            try:
                # Pull tasks
                self._process_tasks()

                # Sleep before next iteration
                time.sleep(5)

            except KeyboardInterrupt:
                logger.info("Shutting down rtx 4090 worker...")
                break
            except Exception as e:
                logger.error(f"Error in worker loop: {e}")
                time.sleep(10)  # Wait longer on errors

    def _process_tasks(self) -> None:
        """Pull and process pending tasks."""
        try:
            # Get device configuration
            device_config = self.config_loader.get_device_config(self.device_id)
            if not device_config:
                logger.warning(f"No configuration found for {self.device_id}")
                return

            # Pull tasks from server
            tasks = self.adapter.pull_tasks("HEAVY_PROCESS_VIDEO", limit=1)

            if not tasks:
                logger.debug("No pending HEAVY_PROCESS_VIDEO tasks")
                return

            # Process each task
            for task in tasks:
                try:
                    logger.info(f"Processing task {task['task_id']}: {task['task_type']}")

                    # Execute the task locally
                    results = self._execute_task(task)

                    # Mark task as complete and publish new tasks if needed
                    self.adapter.mark_task_complete(
                        task["task_id"],
                        results.get("new_tasks", [])
                    )

                    logger.info(f"Completed task {task['task_id']}")

                except Exception as e:
                    logger.error(f"Failed to process task {task['task_id']}: {e}")
                    # Continue with next task even if one fails
                    continue

        except Exception as e:
            logger.error(f"Error processing tasks: {e}")
            raise

    def _execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single HEAVY_PROCESS_VIDEO task.

        Args:
            task_data: Task data from the server

        Returns:
            Dictionary containing results and any new tasks
        """
        task_id = task_data["task_id"]
        video_id = task_data.get("video_id", f"video_{task_id}")

        logger.info(f"Executing HEAVY_PROCESS_VIDEO for task {task_id}, video {video_id}")

        try:
            # In a real implementation, this would:
            # 1. Read preprocessed data from Indoor NAS
            # 2. Perform full-resolution YOLO detection using Jetson proposals
            # 3. GPU-accelerated OCR with multi-frame aggregation
            # 4. GPS timestamp alignment and coordinate mapping
            # 5. Best crop/frame selection algorithms
            # 6. Output comprehensive detection metadata

            # Simulate longer processing delay (GPU heavy work)
            time.sleep(3)

            # Simulate successful heavy processing
            new_tasks = [
                {
                    "task_type": "ARCHIVE_VIDEO",
                    "video_id": video_id,
                    "inputs": [{"device": "rtx_4090", "path": f"/output/detections/{video_id}/"}],
                    "metadata": {"source": "rtx_4090"}
                }
            ]

            return {
                "status": "success",
                "new_tasks": new_tasks
            }

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            raise

    def stop(self) -> None:
        """Stop the worker."""
        self.running = False
        logger.info(f"{self.device_id} rtx 4090 worker stopped")

def main():
    """Main entry point for the rtx 4090 worker."""
    import argparse

    parser = argparse.ArgumentParser(description="RTX 4090 Worker")
    parser.add_argument("--device-id", default="rtx-4090-1", help="Device ID")
    parser.add_argument("--server-url", default="http://localhost:8000", help="Server URL")

    args = parser.parse_args()

    worker = RTX4090Worker(device_id=args.device_id, server_url=args.server_url)
    worker.start()

if __name__ == "__main__":
    main()