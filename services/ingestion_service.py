"""Ingestion Service - Handles indoor NAS video file ingestion and initial task creation."""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import time

from config.loader import ConfigurationLoader
from models.task import Task
from services.task_manager import TaskManager

logger = logging.getLogger(__name__)

class IngestionService:
    """Service for monitoring indoor NAS and creating ingestion tasks."""

    def __init__(self, task_manager: TaskManager, config_loader: ConfigurationLoader):
        """Initialize IngestionService.

        Args:
            task_manager: TaskManager instance for task creation
            config_loader: ConfigurationLoader instance for settings
        """
        self.task_manager = task_manager
        self.config_loader = config_loader
        self.last_scan_time = 0
        self.scan_interval = 60  # seconds

    def monitor_for_new_videos(self, raw_video_dir: Optional[str] = None) -> None:
        """Monitor for new video files and create ingestion tasks.

        Args:
            raw_video_dir: Override directory to scan (for testing)
        """
        config = self.config_loader.get_global_config()
        storage_paths = config.get("storage_paths", {}).get("indoor_nas", {})
        base_path = storage_paths.get("base", "//nas-1/videos/")
        raw_dir = storage_paths.get("raw", "raw/")

        # Use provided override or construct from config
        scan_path = Path(raw_video_dir) if raw_video_dir else Path(base_path + raw_dir)

        logger.info(f"Scanning for new videos in {scan_path}")

        try:
            # List all video files (MP4, AVI, MOV)
            video_extensions = [".mp4", ".avi", ".mov"]
            video_files = []

            for ext in video_extensions:
                video_files.extend(scan_path.glob(f"*{ext}"))
                # Also check subdirectories (trip folders)
                for trip_dir in scan_path.glob("*"):
                    if trip_dir.is_dir():
                        video_files.extend(trip_dir.glob(f"*{ext}"))

            # Sort by modification time to process oldest first
            video_files.sort(key=lambda x: x.stat().st_mtime)

            logger.info(f"Found {len(video_files)} video files")

            # Process each video file
            for video_file in video_files:
                try:
                    self._process_video_file(video_file)
                except Exception as e:
                    logger.error(f"Failed to process {video_file}: {e}")
                    continue

        except FileNotFoundError:
            logger.warning(f"Video directory not found: {scan_path}")
        except Exception as e:
            logger.error(f"Error scanning video directory: {e}")

    def _process_video_file(self, video_file: Path) -> None:
        """Process a single video file and create ingestion task.

        Args:
            video_file: Path to the video file
        """
        # Skip if already processed (check for existing task)
        video_id = self._generate_video_id(video_file)
        existing_task = self.task_manager.get_task_count(
            task_type="INGEST_VIDEO",
            state="pending"
        )

        # Check if we already have a pending task for this video
        for task in self.task_manager.list_tasks(task_type="INGEST_VIDEO", state="pending"):
            if task.video_id == video_id:
                logger.debug(f"Skipping {video_file} - already has pending task")
                return

        # Extract basic metadata from the file
        stat = video_file.stat()
        metadata = {
            "filename": video_file.name,
            "file_size_bytes": stat.st_size,
            "modification_time": stat.st_mtime,
            "access_time": stat.st_atime,
            "video_path": str(video_file)
        }

        # Create inputs and outputs
        inputs = [{
            "device": "indoor_nas",
            "path": str(video_file),
            "type": "video"
        }]

        outputs = []

        # Determine which device should handle ingestion based on config
        device_configs = self.config_loader.get_global_config().get("devices", {})
        for device_id, device_config in device_configs.items():
            if "INGEST_VIDEO" in device_config.get("task_types", []):
                logger.info(f"Creating ingestion task for {video_file}")
                task_data = {
                    "task_type": "INGEST_VIDEO",
                    "video_id": video_id,
                    "inputs": inputs,
                    "outputs": outputs,
                    "metadata": metadata
                }

                try:
                    self.task_manager.create_task(**task_data)
                    logger.info(f"Created INGEST_VIDEO task for {video_file}")
                except Exception as e:
                    logger.error(f"Failed to create ingestion task: {e}")
                break

    def _generate_video_id(self, video_path: Path) -> str:
        """Generate a unique video ID from the path.

        Args:
            video_path: Path to the video file

        Returns:
            Generated video ID
        """
        # Use parent directory name (trip) + filename without extension
        parent = video_path.parent.name
        name = video_path.stem
        return f"{parent}_{name}"

    def create_ingestion_task(self, video_path: str) -> Optional[Task]:
        """Create an ingestion task for a specific video path.

        Args:
            video_path: Path to the video file

        Returns:
            Created Task object or None if failed
        """
        path = Path(video_path)
        if not path.exists():
            logger.error(f"Video file not found: {video_path}")
            return None

        try:
            metadata = {
                "filename": path.name,
                "file_size_bytes": path.stat().st_size,
                "modification_time": path.stat().st_mtime,
                "video_path": str(path)
            }

            inputs = [{
                "device": "indoor_nas",
                "path": str(path),
                "type": "video"
            }]

            video_id = self._generate_video_id(path)

            task_data = {
                "task_type": "INGEST_VIDEO",
                "video_id": video_id,
                "inputs": inputs,
                "outputs": [],
                "metadata": metadata
            }

            return self.task_manager.create_task(**task_data)
        except Exception as e:
            logger.error(f"Failed to create ingestion task for {video_path}: {e}")
            return None

    def run_continuous(self, interval_seconds: int = 60) -> None:
        """Run the ingestion service continuously.

        Args:
            interval_seconds: Scan interval in seconds
        """
        self.scan_interval = interval_seconds
        logger.info(f"Starting continuous monitoring (interval: {interval_seconds}s)")

        while True:
            try:
                start_time = time.time()
                self.monitor_for_new_videos()

                # Sleep for the remaining interval time
                elapsed = time.time() - start_time
                sleep_time = max(0, self.scan_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                logger.info("Stopping ingestion service")
                break
            except Exception as e:
                logger.error(f"Error in continuous monitoring: {e}")
                time.sleep(self.scan_interval)  # Wait before retrying

if __name__ == "__main__":
    # Example usage when run directly
    from db.init_db import init_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Setup database
    engine = create_engine("sqlite:///tasks.db")
    Session = sessionmaker(bind=engine)
    session = Session()

    # Initialize DB (create tables if needed)
    init_db(engine)

    # Create services
    config_loader = ConfigurationLoader()
    task_manager = TaskManager(session)
    ingestion_service = IngestionService(task_manager, config_loader)

    # Run continuously
    ingestion_service.run_continuous()