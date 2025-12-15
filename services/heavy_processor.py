"""Heavy Processor Service - Full-resolution GPU processing on RTX 4090."""

import os
import cv2
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import time

import numpy as np

from config.loader import ConfigurationLoader
from models.task import Task
from services.task_manager import TaskManager

logger = logging.getLogger(__name__)

class HeavyProcessor:
    """Service for heavy GPU-accelerated video processing."""

    def __init__(self, task_manager: TaskManager, config_loader: ConfigurationLoader):
        """Initialize HeavyProcessor.

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
        """Get pending heavy processing tasks.

        Args:
            limit: Maximum number of tasks to retrieve

        Returns:
            List of pending Task objects
        """
        return self.task_manager.get_pending_tasks(
            task_type="HEAVY_PROCESS_VIDEO",
            limit=limit,
            device_capabilities={"cuda_cores": 16384}
        )

    def process_task(self, task: Task) -> Dict[str, Any]:
        """Process a single heavy processing task.

        Args:
            task: Task to process

        Returns:
            Dictionary with processing results
        """
        logger.info(f"Processing heavy task {task.task_id} for video {task.video_id}")

        # Get inputs from the task
        if not task.inputs:
            raise ValueError("No input files specified in task")

        video_path = None
        preproc_data = None

        for input_item in task.inputs:
            if input_item.get("type") == "video":
                video_path = input_item["path"]
            elif input_item.get("type") == "metadata" and "preproc" in input_item.get("path", ""):
                # Try to load preproc data
                try:
                    with open(input_item["path"], 'r') as f:
                        preproc_data = json.load(f)
                except Exception as e:
                    logger.warning(f"Could not load preproc data: {e}")

        if not video_path:
            raise ValueError("No video file found in task inputs")

        # Load device configuration with defaults
        config = self.config_loader.get_global_config()
        processing_config = self.device_config.get("processing", {}) if self.device_config else {}

        yolo_model_path = processing_config.get(
            "yolo_model_path",
            "/models/yolov8n.pt"
        )
        ocr_model_path = processing_config.get(
            "ocr_model_path",
            "/models/plate.pt"
        )
        max_frames_per_batch = processing_config.get(
            "max_frames_per_batch",
            16
        )
        gps_alignment_tolerance_ms = processing_config.get(
            "gps_alignment_tolerance_ms",
            200
        )

        # Process the video using preproc data
        results = {
            "video_id": task.video_id,
            "task_id": task.task_id,
            "detections": [],
            "plate_readings": [],
            "gps_alignments": [],
            "processing_time_ms": 0,
            "error": None,
            "stats": {}
        }

        start_time = time.time()

        try:
            # Open video file
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise IOError(f"Could not open video file: {video_path}")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            results["stats"]["total_frames"] = total_frames
            results["stats"]["fps"] = fps

            logger.info(
                f"Processing video: {total_frames} frames, "
                f"{fps:.2f} fps"
            )

            # Process frames based on preproc data if available
            if preproc_data and "plate_candidates" in preproc_data:
                plate_candidates = preproc_data["plate_candidates"]

                logger.info(f"Processing {len(plate_candidates)} plate candidates")

                for candidate_idx, candidate in enumerate(plate_candidates):
                    try:
                        frame_num = candidate["frame"]
                        region = candidate["plate_region"]

                        # Set video position to the right frame
                        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num - 1)

                        ret, frame = cap.read()
                        if not ret:
                            logger.warning(f"Could not read frame {frame_num}")
                            continue

                        # Crop plate region (slightly expanded)
                        x = int(region["x"])
                        y = int(region["y"])
                        w = int(region["width"])
                        h = int(region["height"])

                        # Expand the region by 20% on each side
                        expand_x = int(w * 0.2)
                        expand_y = int(h * 0.2)

                        crop_x1 = max(0, x - expand_x)
                        crop_y1 = max(0, y - expand_y)
                        crop_x2 = min(frame.shape[1], x + w + expand_x)
                        crop_y2 = min(frame.shape[0], y + h + expand_y)

                        plate_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]

                        # Run YOLO detection on the crop
                        yolo_detections = self._run_yolo_detection(plate_crop)
                        logger.info(f"Frame {frame_num}: YOLO detected {len(yolo_detections)} objects")

                        # Run OCR if we have vehicle/license plate detections
                        for det in yolo_detections:
                            if det["class_id"] == 0:  # License plate class
                                ocr_result = self._run_ocr_on_crop(plate_crop)
                                plate_text = ocr_result.get("text", "")

                                detection = {
                                    "frame": frame_num,
                                    "region": region,
                                    "expanded_region": {
                                        "x": crop_x1,
                                        "y": crop_y1,
                                        "width": crop_x2 - crop_x1,
                                        "height": crop_y2 - crop_y1
                                    },
                                    "confidence": float(det["confidence"]),
                                    "class_id": det["class_id"],
                                    "plate_text": plate_text,
                                    "ocr_confidence": ocr_result.get("confidence", 0.0)
                                }

                                results["detections"].append(detection)

                                if plate_text:
                                    results["plate_readings"].append({
                                        "frame": frame_num,
                                        "text": plate_text,
                                        "confidence": float(ocr_result.get("confidence", 0.0))
                                    })

                    except Exception as e:
                        logger.error(f"Error processing candidate {candidate_idx}: {e}")
                        continue

            cap.release()

        except Exception as e:
            results["error"] = str(e)
            logger.error(f"Error in heavy processing: {e}")
            raise
        finally:
            elapsed_time = (time.time() - start_time) * 1000
            results["processing_time_ms"] = elapsed_time
            logger.info(f"Heavy processing completed in {elapsed_time:.2f}ms")

        return results

    def _run_yolo_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run YOLO detection on a frame.

        Args:
            frame: Frame image as numpy array

        Returns:
            List of detection dictionaries
        """
        # This is a placeholder for actual YOLO implementation
        # In production, this would use the YOLOv8 model

        # Mock implementation for development/testing
        detections = []

        # Simulate vehicle and plate detections
        import random

        # Check if there's a license plate in this region (simulated)
        has_plate = random.random() < 0.7  # 70% chance of having a plate

        if has_plate:
            detections.append({
                "bbox": [
                    random.uniform(0.2, 0.5),
                    random.uniform(0.4, 0.6),
                    random.uniform(0.3, 0.5),
                    random.uniform(0.2, 0.3)
                ],
                "confidence": random.uniform(0.7, 0.95),
                "class_id": 0  # License plate class
            })

        return detections

    def _run_ocr_on_crop(self, crop: np.ndarray) -> Dict[str, Any]:
        """Run OCR on a plate crop.

        Args:
            crop: Crop image as numpy array

        Returns:
            Dictionary with OCR results
        """
        # This is a placeholder for actual OCR implementation
        # In production, this would use the plate recognition model

        # Mock implementation for development/testing
        import random

        return {
            "text": self._generate_mock_plate_text(),
            "confidence": random.uniform(0.85, 0.99),
            "characters": []
        }

    def _generate_mock_plate_text(self) -> str:
        """Generate mock license plate text for testing."""
        import random
        import string

        # Generate realistic-looking plate (e.g., "ABC1234")
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        numbers = ''.join(random.choices(string.digits, k=4))

        return f"{letters}{numbers}"

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

        # Create directories for different output types
        plate_crops_dir = Path(output_dir) / "plate_crops"
        plate_crops_dir.mkdir(exist_ok=True)

        # Write JSON metadata with all detections
        json_path = Path(output_dir) / f"{video_id}_detections.json"
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)

        # Generate plate crop images (first 5)
        crops_generated = []
        for i, detection in enumerate(results["detections"][:5]):
            try:
                # In a real implementation, we would extract the actual crop here
                # For now, create placeholder files
                crop_path = plate_crops_dir / f"plate_{i}.jpg"
                with open(crop_path, 'w') as f:  # Create empty file as placeholder
                    pass

                crops_generated.append(str(crop_path))
            except Exception as e:
                logger.warning(f"Failed to create plate crop {i}: {e}")
                continue

        outputs = [
            {
                "device": "indoor_nas",
                "path": str(json_path),
                "type": "metadata"
            }
        ]

        if crops_generated:
            # Add first crop as representative output
            outputs.append({
                "device": "rtx_4090_local",
                "path": crops_generated[0],
                "type": "plate_crops",
                "temporary": True
            })

        return outputs

    def execute_task(self, task_id: int) -> Dict[str, Any]:
        """Execute a heavy processing task by ID.

        Args:
            task_id: Task ID to execute

        Returns:
            Dictionary with execution results
        """
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        logger.info(f"Executing heavy processing task {task_id}")

        try:
            # Process the task
            results = self.process_task(task)

            # Generate outputs (would use actual scratch space in production)
            output_dir = f"/tmp/heavy_{task.video_id}"
            outputs = self.generate_outputs(results, output_dir)

            # Create downstream ARCHIVE_VIDEO task if we have detections
            new_tasks = []
            if results["detections"]:
                logger.info(f"Found {len(results['detections'])} total detections")

                # Update task with outputs and create archive task
                task.outputs = outputs

                # Create metadata for archive task
                archive_task_metadata = {
                    "heavy_results": results,
                    "detection_count": len(results["detections"]),
                    "plate_reading_count": len(results["plate_readings"])
                }

                new_tasks.append({
                    "task_type": "ARCHIVE_VIDEO",
                    "video_id": task.video_id,
                    "inputs": [
                        {"device": input_item["device"], "path": input_item["path"], "type": input_item["type"]}
                        for input_item in task.inputs
                    ] + outputs,
                    "outputs": [],
                    "metadata": archive_task_metadata
                })

            # Mark task as complete and publish new tasks if any
            self.task_manager.mark_task_complete(task_id, new_tasks)

            logger.info(f"Completed heavy processing task {task_id}")
            return {
                "success": True,
                "results": results,
                "new_tasks_created": len(new_tasks)
            }

        except Exception as e:
            logger.error(f"Failed to execute heavy processing task {task_id}: {e}")
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
        """Run the heavy processor service continuously."""
        logger.info("Starting Heavy Processor Service")

        while True:
            try:
                # Get pending tasks
                tasks = self.get_pending_tasks(limit=1)

                if not tasks:
                    logger.debug("No pending heavy processing tasks")
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
                logger.info("Stopping Heavy Processor Service")
                break
            except Exception as e:
                logger.error(f"Error in heavy processor loop: {e}")
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
    heavy_processor = HeavyProcessor(task_manager, config_loader)

    # Run continuously
    heavy_processor.run()