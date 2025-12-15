"""Shed NAS Worker - Pulls ARCHIVE_VIDEO tasks for long-term storage."""

import time
import logging
from typing import Dict, Any

from config.loader import ConfigurationLoader
from services.shed_nas_adapter import ShedNASAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class ShedNASWorker:
    """Worker that pulls and processes ARCHIVE_VIDEO tasks for Shed NAS."""

    def __init__(self, device_id: str = "shed-nas-1", server_url: str = "http://localhost:8000"):
        """Initialize Shed NAS Worker.

        Args:
            device_id: Unique identifier for this shed NAS worker
            server_url: URL of the main server
        """
        self.device_id = device_id
        self.server_url = server_url.rstrip('/')
        self.config_loader = ConfigurationLoader()
        self.adapter = ShedNASAdapter(device_id, config=self.config_loader.get_device_config(device_id))
        self.running = False

    def start(self) -> None:
        """Start the worker loop."""
        logger.info(f"Starting {self.device_id} shed nas worker")
        self.running = True

        while self.running:
            try:
                # Pull tasks
                self._process_tasks()

                # Sleep before next iteration
                time.sleep(5)

            except KeyboardInterrupt:
                logger.info("Shutting down shed nas worker...")
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
            tasks = self.adapter.pull_tasks("ARCHIVE_VIDEO", limit=1)

            if not tasks:
                logger.debug("No pending ARCHIVE_VIDEO tasks")
                return

            # Process each task
            for task in tasks:
                try:
                    logger.info(f"Processing task {task['task_id']}: {task['task_type']}")

                    # Execute the task locally
                    results = self._execute_task(task)

                    # Mark task as complete (no new tasks from archival)
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
        """Execute a single ARCHIVE_VIDEO task.

        Args:
            task_data: Task data from the server

        Returns:
            Dictionary containing results and any new tasks
        """
        task_id = task_data["task_id"]
        video_id = task_data.get("video_id", f"video_{task_id}")

        logger.info(f"Executing ARCHIVE_VIDEO for task {task_id}, video {video_id}")

        try:
            # In a real implementation, this would:
            # 1. Read detection outputs from RTX 4090
            # 2. Store finalized media (de-resolved videos, plate crops)
            # 3. Provide static file serving for WebUI
            # 4. Implement retention policies

            # Simulate processing delay
            time.sleep(1)

            # Simulate successful archival (no new tasks from final stage)
            return {
                "status": "success",
                "new_tasks": []
            }

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            raise

    def stop(self) -> None:
        """Stop the worker."""
        self.running = False
        logger.info(f"{self.device_id} shed nas worker stopped")

def main():
    """Main entry point for the shed NAS worker."""
    import argparse

    parser = argparse.ArgumentParser(description="Shed NAS Worker")
    parser.add_argument("--device-id", default="shed-nas-1", help="Device ID")
    parser.add_argument("--server-url", default="http://localhost:8000", help="Server URL")

    args = parser.parse_args()

    worker = ShedNASWorker(device_id=args.device_id, server_url=args.server_url)
    worker.start()

if __name__ == "__main__":
    main()