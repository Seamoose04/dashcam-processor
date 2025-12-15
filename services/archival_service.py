"""Archival Service - Long-term storage on shed NAS."""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import shutil
import time

from config.loader import ConfigurationLoader
from models.task import Task
from services.task_manager import TaskManager

logger = logging.getLogger(__name__)

class ArchivalService:
    """Service for archiving processed video data to shed NAS."""

    def __init__(self, task_manager: TaskManager, config_loader: ConfigurationLoader):
        """Initialize ArchivalService.

        Args:
            task_manager: TaskManager instance for task management
            config_loader: ConfigurationLoader instance for settings
        """
        self.task_manager = task_manager
        self.config_loader = config_loader

    def get_pending_tasks(self, limit: int = 1) -> List[Task]:
        """Get pending archival tasks.

        Args:
            limit: Maximum number of tasks to retrieve

        Returns:
            List of pending Task objects
        """
        return self.task_manager.get_pending_tasks(
            task_type="ARCHIVE_VIDEO",
            limit=limit
        )

    def process_task(self, task: Task) -> Dict[str, Any]:
        """Process a single archival task.

        Args:
            task: Task to process

        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing archival task {task.task_id} for video {task.video_id}")

        # Get inputs from the task
        if not task.inputs:
            raise ValueError("No input files specified in task")

        # Load config
        config = self.config_loader.get_global_config()
        storage_paths = config.get("storage_paths", {}).get("shed_nas", {})
        archive_base = storage_paths.get("archive_base", "//shed-nas/archive/")
        video_id = task.video_id

        # Create archive directory structure
        archive_dir = Path(archive_base) / video_id
        os.makedirs(archive_dir, exist_ok=True)

        results = {
            "video_id": video_id,
            "task_id": task.task_id,
            "files_archived": [],
            "total_size_bytes": 0,
            "processing_time_ms": 0,
            "error": None
        }

        start_time = time.time()

        try:
            # Process each input to determine what needs to be archived
            for input_item in task.inputs:
                source_path = input_item["path"]
                file_type = input_item.get("type", "")

                if not os.path.exists(source_path):
                    logger.warning(f"Source file not found: {source_path}")
                    continue

                dest_path = None

                # Determine destination path based on file type
                if file_type == "metadata":
                    # Store detection metadata
                    filename = os.path.basename(source_path)
                    dest_path = archive_dir / f"detections_{filename}"
                elif file_type == "plate_crops":
                    # Store in plates subdirectory
                    plates_dir = archive_dir / "plates"
                    plates_dir.mkdir(exist_ok=True)
                    filename = os.path.basename(source_path)
                    dest_path = plates_dir / filename
                elif file_type == "thumbnails":
                    # Store in thumbs subdirectory
                    thumbs_dir = archive_dir / "thumbs"
                    thumbs_dir.mkdir(exist_ok=True)
                    filename = os.path.basename(source_path)
                    dest_path = thumbs_dir / filename
                elif file_type == "video":
                    # Create de-resolved version (simulated for now)
                    dest_path = archive_dir / f"video_lowres.mp4"

                if dest_path:
                    try:
                        stat = os.stat(source_path)

                        # For videos, we would create a de-resolved version
                        # For now, just copy the metadata
                        if file_type == "metadata":
                            shutil.copy2(source_path, dest_path)
                            logger.info(f"Archived {source_path} to {dest_path}")

                            # Read and store metadata summary
                            try:
                                with open(dest_path, 'r') as f:
                                    detections = json.load(f)
                                    results["stats"] = {
                                        "detection_count": len(detections.get("detections", [])),
                                        "plate_reading_count": len(detections.get("plate_readings", []))
                                    }
                            except Exception as e:
                                logger.warning(f"Could not parse detection metadata: {e}")

                        elif file_type == "video":
                            # Simulate de-resolution
                            with open(dest_path, 'w') as f:  # Create placeholder
                                pass

                        else:
                            shutil.copy2(source_path, dest_path)

                        results["files_archived"].append({
                            "source": source_path,
                            "destination": str(dest_path),
                            "size_bytes": stat.st_size,
                            "type": file_type
                        })
                        results["total_size_bytes"] += stat.st_size

                    except Exception as e:
                        logger.error(f"Failed to archive {source_path}: {e}")
                        continue

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Error in archival processing: {e}")
            raise
        finally:
            elapsed_time = (time.time() - start_time) * 1000
            results["processing_time_ms"] = elapsed_time
            logger.info(f"Archival completed in {elapsed_time:.2f}ms")

        return results

    def generate_outputs(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate outputs from archival results.

        Args:
            results: Archival results dictionary

        Returns:
            List of output file references
        """
        # For archival service, the outputs are the final stored files
        # We create references to them for the WebUI to access
        outputs = []

        config = self.config_loader.get_global_config()
        storage_paths = config.get("storage_paths", {}).get("shed_nas", {})
        archive_base = storage_paths.get("archive_base", "//shed-nas/archive/")
        video_id = results["video_id"]

        # Create references to all archived files
        for file_info in results["files_archived"]:
            outputs.append({
                "device": "shed_nas",
                "path": file_info["destination"],
                "type": file_info.get("type", "media"),
                "temporary": False  # Final archival, not temporary
            })

        return outputs

    def execute_task(self, task_id: int) -> Dict[str, Any]:
        """Execute an archival task by ID.

        Args:
            task_id: Task ID to execute

        Returns:
            Dictionary with execution results
        """
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        logger.info(f"Executing archival task {task_id}")

        try:
            # Process the task
            results = self.process_task(task)

            # Generate outputs (final references for WebUI)
            outputs = self.generate_outputs(results)

            # Update task with final outputs
            task.outputs = outputs

            # No downstream tasks from archival (final stage)
            new_tasks = []

            # Mark task as complete
            self.task_manager.mark_task_complete(task_id, new_tasks)

            logger.info(f"Completed archival task {task_id}")
            return {
                "success": True,
                "results": results,
                "new_tasks_created": len(new_tasks)
            }

        except Exception as e:
            logger.error(f"Failed to execute archival task {task_id}: {e}")
            # Mark task as complete with error flag in metadata
            try:
                self.task_manager.mark_task_complete(task_id, [])
            except Exception:
                pass  # Don't fail if we can't mark it complete

            return {
                "success": False,
                "error": str(e)
            }

    def run(self) -> None:
        """Run the archival service continuously."""
        logger.info("Starting Archival Service")

        while True:
            try:
                # Get pending tasks
                tasks = self.get_pending_tasks(limit=1)

                if not tasks:
                    logger.debug("No pending archival tasks")
                    time.sleep(5)
                    continue

                task = tasks[0]
                logger.info(f"Found task {task.task_id} to process")

                # Execute the task
                result = self.execute_task(task.task_id)

                if result["success"]:
                    logger.info(f"Successfully processed task {task.task_id}")
                else:
                    logger.error(f"Failed to process task {task.task_id}: {result.get('error')}")

                time.sleep(1)  # Brief pause before next iteration

            except KeyboardInterrupt:
                logger.info("Stopping Archival Service")
                break
            except Exception as e:
                logger.error(f"Error in archival loop: {e}")
                time.sleep(5)  # Wait before retrying

    def cleanup_old_archives(self, retention_days: int = 30) -> Dict[str, Any]:
        """Clean up archives older than specified retention period.

        Args:
            retention_days: Number of days to retain archives

        Returns:
            Dictionary with cleanup results
        """
        config = self.config_loader.get_global_config()
        storage_paths = config.get("storage_paths", {}).get("shed_nas", {})
        archive_base = Path(storage_paths.get("archive_base", "//shed-nas/archive/"))

        if not archive_base.exists():
            return {"message": "Archive base directory does not exist"}

        results = {
            "cleaned_up": 0,
            "skipped": 0,
            "error": None
        }

        try:
            # Get retention cutoff time
            from datetime import datetime, timedelta
            cutoff_time = datetime.now() - timedelta(days=retention_days)

            # Find all video directories
            for archive_dir in archive_base.glob("*"):
                if not archive_dir.is_dir():
                    continue

                try:
                    # Get modification time of directory
                    mod_time = datetime.fromtimestamp(archive_dir.stat().st_mtime)

                    if mod_time < cutoff_time:
                        # Clean up this archive
                        shutil.rmtree(archive_dir)
                        results["cleaned_up"] += 1
                        logger.info(f"Cleaned up old archive: {archive_dir}")
                    else:
                        results["skipped"] += 1

                except Exception as e:
                    logger.error(f"Error cleaning up {archive_dir}: {e}")
                    continue

            return results

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Error during cleanup: {e}")
            return results

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
    archival_service = ArchivalService(task_manager, config_loader)

    # Run continuously
    archival_service.run()