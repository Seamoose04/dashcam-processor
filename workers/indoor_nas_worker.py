"""Indoor NAS Worker - Pulls INGEST_VIDEO tasks for video ingestion."""

import time
import logging
from typing import Dict, Any

from config.loader import ConfigurationLoader
from services.indoor_nas_adapter import IndoorNASAdapter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class IndoorNASWorker:
    """Worker that pulls and processes INGEST_VIDEO tasks from Indoor NAS."""

    def __init__(self, device_id: str = "indoor-nas-1", server_url: str = "http://localhost:8000"):
        """Initialize Indoor NAS Worker.

        Args:
            device_id: Unique identifier for this indoor NAS worker
            server_url: URL of the main server
        """
        self.device_id = device_id
        self.server_url = server_url.rstrip('/')
        self.config_loader = ConfigurationLoader()
        self.adapter = IndoorNASAdapter(device_id, config=self.config_loader.get_device_config(device_id))
        self.running = False

    def start(self) -> None:
        """Start the worker loop."""
        logger.info(f"Starting {self.device_id} indoor nas worker")
        self.running = True

        while self.running:
            try:
                # Pull tasks
                self._process_tasks()

                # Sleep before next iteration
                time.sleep(5)

            except KeyboardInterrupt:
                logger.info("Shutting down indoor nas worker...")
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
            tasks = self.adapter.pull_tasks("INGEST_VIDEO", limit=1)

            if not tasks:
                logger.debug("No pending INGEST_VIDEO tasks")
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
        """Execute a single INGEST_VIDEO task.

        Args:
            task_data: Task data from the server

        Returns:
            Dictionary containing results and any new tasks
        """
        task_id = task_data["task_id"]
        video_path = None  # Would be extracted from task metadata in real implementation

        logger.info(f"Executing INGEST_VIDEO for task {task_id}")

        try:
            # In a real implementation, this would:
            # 1. Monitor Indoor NAS for new video files
            # 2. Create INGEST_VIDEO tasks upon detection
            # 3. Extract basic metadata (filename, size, timestamp)
            # 4. Trigger preprocessing workflow via task creation

            # Simulate processing delay
            time.sleep(2)

            # Simulate successful ingestion
            new_tasks = [
                {
                    "task_type": "PREPROCESS_VIDEO",
                    "video_id": f"video_{task_id}",
                    "inputs": [{"device": "indoor_nas", "path": "/videos/raw/video.mp4"}],
                    "metadata": {"source": "indoor_nas"}
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
        logger.info(f"{self.device_id} indoor nas worker stopped")

def main():
    """Main entry point for the indoor NAS worker."""
    import argparse

    parser = argparse.ArgumentParser(description="Indoor NAS Worker")
    parser.add_argument("--device-id", default="indoor-nas-1", help="Device ID")
    parser.add_argument("--server-url", default="http://localhost:8000", help="Server URL")

    args = parser.parse_args()

    worker = IndoorNASWorker(device_id=args.device_id, server_url=args.server_url)
    worker.start()

if __name__ == "__main__":
    main()