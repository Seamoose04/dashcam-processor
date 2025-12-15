"""Preprocessor Service - Lightweight processing on Jetson Coral with Coral TPU."""

import os
import cv2
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import time
import subprocess

import numpy as np
from PIL import Image

from config.loader import ConfigurationLoader
from models.task import Task
from services.task_manager import TaskManager

logger = logging.getLogger(__name__)

class Preprocessor:
    """Service for lightweight video preprocessing using Jetson Coral."""

    def __init__(self, task_manager: TaskManager, config_loader: ConfigurationLoader):
        """Initialize Preprocessor.

        Args:
            task_manager: TaskManager instance for task management
            config_loader: ConfigurationLoader instance for settings
        """
        self.task_manager = task_manager
        self.config_loader = config_loader

        # Load device-specific configuration
        self.device_config = None
        try:
            import socket
            hostname = socket.gethostname()
            self.device_config = config_loader.get_device_config(hostname)
        except Exception as e:
            logger.warning(f"Could not load device-specific config: {e}")

    def get_pending_tasks(self, limit: int = 1) -> List[Task]:
        """Get pending preprocessing tasks.

        Args:
            limit: Maximum number of tasks to retrieve

        Returns:
            List of pending Task objects
        """
        return self.task_manager.get_pending_tasks(
            task_type="PREPROCESS_VIDEO",
            limit=limit,
            device_capabilities={"coral_tpu": True}
        )

    def process_task(self, task: Task) -> Dict[str, Any]:
        """Process a single preprocessing task.

        Args:
            task: Task to process

        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing task {task.task_id} for video {task.video_id}")

        # Get inputs from the task
        if not task.inputs:
            raise ValueError("No input files specified in task")

        video_path = None
        for input_item in task.inputs:
            if input_item.get("type") == "video":
                video_path = input_item["path"]
                break

        if not video_path:
            raise ValueError("No video file found in task inputs")

        # Load device configuration with defaults
        config = self.config_loader.get_global_config()
        processing_config = self.device_config.get("processing", {}) if self.device_config else {}

        frame_resolution = processing_config.get(
            "frame_extraction_resolution",
            "640x480"
        )
        motion_threshold = processing_config.get(
            "motion_threshold",
            0.15
        )
        min_plate_confidence = processing_config.get(
            "min_plate_confidence",
            0.6
        )

        # Parse resolution
        try:
            width, height = map(int, frame_resolution.split("x"))
        except ValueError:
            logger.warning(f"Invalid resolution format: {frame_resolution}, using default 640x480")
            width, height = 640, 480

        # Process the video
        results = {
            "video_id": task.video_id,
            "task_id": task.task_id,
            "total_frames": 0,
            "selected_frames": 0,
            "plate_candidates": [],
            "motion_stats": [],
            "processing_time_ms": 0,
            "error": None
        }

        start_time = time.time()

        try:
            # Open video file
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise IOError(f"Could not open video file: {video_path}")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            duration = total_frames / fps

            results["total_frames"] = total_frames
            results["duration_seconds"] = duration
            results["fps"] = fps

            logger.info(
                f"Processing video: {total_frames} frames, "
                f"{duration:.2f}s duration, {fps:.2f} fps"
            )

            # Frame selection parameters
            frame_step = max(1, int(total_frames * 0.95))  # Keep top 5% of frames based on motion
            current_frame = 0

            # For motion detection: track previous frame
            prev_gray = None
            frame_count = 0

            while cap.isOpened() and current_frame < total_frames:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

                # Skip frames based on step (but still check motion)
                if frame_count % 5 != 0:  # Check every 5th frame for motion
                    continue

                # Convert to grayscale for motion detection
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if prev_gray is not None:
                    # Calculate optical flow (motion)
                    flow = cv2.calcOpticalFlowFarneback(
                        prev_gray, gray, None,
                        0.5, 3, 15, 3, 5
                    )
                    magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                    motion_score = np.mean(magnitude)

                    results["motion_stats"].append({
                        "frame": current_frame,
                        "motion_score": float(motion_score)
                    })

                    # Select frame if motion exceeds threshold
                    if motion_score > motion_threshold:
                        self._process_frame(
                            frame, current_frame, task.video_id,
                            width, height, min_plate_confidence,
                            results["plate_candidates"]
                        )
                        results["selected_frames"] += 1

                prev_gray = gray

            cap.release()

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Error processing video: {e}")
            raise

        finally:
            elapsed_time = (time.time() - start_time) * 1000
            results["processing_time_ms"] = elapsed_time
            logger.info(f"Processing completed in {elapsed_time:.2f}ms")

        return results

    def _process_frame(
        self,
        frame: np.ndarray,
        frame_num: int,
        video_id: str,
        target_width: int,
        target_height: int,
        min_confidence: float,
        plate_candidates: List[Dict[str, Any]]
    ) -> None:
        """Process a single frame for plate detection.

        Args:
            frame: Frame image as numpy array
            frame_num: Frame number in video
            video_id: Video ID
            target_width: Target width for resizing
            target_height: Target height for resizing
            min_confidence: Minimum confidence threshold for plates
            plate_candidates: List to append candidates to
        """
        try:
            # Resize frame for processing
            small_frame = cv2.resize(frame, (target_width, target_height))
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            # Run Coral TPU inference for plate detection
            detections = self._run_coral_inference(rgb_small_frame)

            # Filter and store plate candidates
            for detection in detections:
                if detection["confidence"] >= min_confidence:
                    candidate = {
                        "frame": frame_num,
                        "plate_region": {
                            "x": int(detection["bbox"][0] * target_width),
                            "y": int(detection["bbox"][1] * target_height),
                            "width": int(detection["bbox"][2] * target_width),
                            "height": int(detection["bbox"][3] * target_height)
                        },
                        "confidence": float(detection["confidence"]),
                        "resolution": f"{target_width}x{target_height}"
                    }
                    plate_candidates.append(candidate)

        except Exception as e:
            logger.error(f"Error processing frame {frame_num}: {e}")

    def _run_coral_inference(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run Coral TPU inference on a frame.

        Args:
            frame: RGB frame as numpy array

        Returns:
            List of detection dictionaries
        """
        # This is a placeholder for actual Coral TPU integration
        # In production, this would use the edgetpu library

        # Mock implementation for development/testing
        detections = []

        # Simulate some plate detections (for testing)
        import random
        num_detections = random.randint(0, 3)

        for i in range(num_detections):
            confidence = random.uniform(0.5, 0.95)
            if confidence > 0.6:  # Only keep high-confidence detections
                detections.append({
                    "bbox": [
                        random.uniform(0.1, 0.8),
                        random.uniform(0.3, 0.7),
                        random.uniform(0.2, 0.4),
                        random.uniform(0.15, 0.3)
                    ],
                    "confidence": confidence,
                    "class_id": 0
                })

        return detections

    def generate_outputs(self, results: Dict[str, Any], output_dir: str) -> List[Dict[str, Any]]:
        """Generate outputs from processing results.

        Args:
            results: Processing results dictionary
            output_dir: Directory to write outputs to

        Returns:
            List of output file references
        """
        os.makedirs(output_dir, exist_ok=True)
        video_id = results["video_id"]

        # Write JSON metadata
        json_path = Path(output_dir) / f"{video_id}_preproc.json"
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)

        # Generate thumbnails for plate candidates (first 3)
        thumb_dir = Path(output_dir) / "thumbs"
        thumb_dir.mkdir(exist_ok=True)

        thumbs_generated = []
        for i, candidate in enumerate(results["plate_candidates"][:3]):  # Max 3 thumbs
            try:
                # In a real implementation, we would extract the actual frame here
                # For now, create a placeholder thumbnail
                thumb_path = thumb_dir / f"thumb_{i}.jpg"
                with open(thumb_path, 'w') as f:  # Create empty file as placeholder
                    pass
                thumbs_generated.append(str(thumb_path))
            except Exception as e:
                logger.warning(f"Failed to create thumbnail {i}: {e}")
                continue

        outputs = [
            {
                "device": "indoor_nas",
                "path": str(json_path),
                "type": "metadata"
            }
        ]

        if thumbs_generated:
            outputs.append({
                "device": "jetson_local",
                "path": str(thumb_dir / "thumb_0.jpg"),  # First thumb as example
                "type": "thumbnails",
                "temporary": True
            })

        return outputs

    def execute_task(self, task_id: int) -> Dict[str, Any]:
        """Execute a preprocessing task by ID.

        Args:
            task_id: Task ID to execute

        Returns:
            Dictionary with execution results
        """
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        logger.info(f"Executing preprocessing task {task_id}")

        try:
            # Process the task
            results = self.process_task(task)

            # Generate outputs (would use actual scratch space in production)
            output_dir = f"/tmp/preproc_{task.video_id}"
            outputs = self.generate_outputs(results, output_dir)

            # Create downstream HEAVY_PROCESS_VIDEO task
            new_tasks = []
            if results["plate_candidates"]:
                logger.info(f"Found {len(results['plate_candidates'])} plate candidates")

                # Update task with outputs and create heavy processing task
                task.outputs = outputs

                # Create metadata for heavy processing task
                heavy_task_metadata = {
                    "preproc_results": results,
                    "plate_count": len(results["plate_candidates"]),
                    "selected_frames": results["selected_frames"],
                    "total_frames": results["total_frames"]
                }

                new_tasks.append({
                    "task_type": "HEAVY_PROCESS_VIDEO",
                    "video_id": task.video_id,
                    "inputs": [
                        {"device": "indoor_nas", "path": input_item["path"], "type": input_item["type"]}
                        for input_item in task.inputs
                    ] + outputs,
                    "outputs": [],
                    "metadata": heavy_task_metadata
                })

            # Mark task as complete and publish new tasks if any
            self.task_manager.mark_task_complete(task_id, new_tasks)

            logger.info(f"Completed preprocessing task {task_id}")
            return {
                "success": True,
                "results": results,
                "new_tasks_created": len(new_tasks)
            }

        except Exception as e:
            logger.error(f"Failed to execute preprocessing task {task_id}: {e}")
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
        """Run the preprocessor service continuously."""
        logger.info("Starting Preprocessor Service")

        while True:
            try:
                # Get pending tasks
                tasks = self.get_pending_tasks(limit=1)

                if not tasks:
                    logger.debug("No pending preprocessing tasks")
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
                logger.info("Stopping Preprocessor Service")
                break
            except Exception as e:
                logger.error(f"Error in preprocessor loop: {e}")
                time.sleep(5)  # Wait before retrying

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
    preprocessor = Preprocessor(task_manager, config_loader)

    # Run continuously
    preprocessor.run()