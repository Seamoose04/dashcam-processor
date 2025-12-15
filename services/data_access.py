"""Data access layer for WebUI - provides services to retrieve metadata from database
and get media files from NAS filesystem."""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from sqlalchemy import create_engine, desc, asc, or_, and_
from sqlalchemy.orm import sessionmaker

from models.task import Task, InputOutput
from config.loader import ConfigLoader

logger = logging.getLogger(__name__)

class DataAccessLayer:
    """Data access layer for WebUI to query metadata and locate media files."""

    def __init__(self, db_url: str = None, config_loader: ConfigLoader = None):
        """
        Initialize the data access layer.

        Args:
            db_url: Database connection URL (defaults to config)
            config_loader: Configuration loader instance
        """
        self.config_loader = config_loader or ConfigLoader()
        self.db_url = db_url or self.config_loader.get_database_url()
        self.engine = create_engine(self.db_url)

        # Create session factory
        Session = sessionmaker(bind=self.engine)
        self.Session = Session

    def get_video_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete metadata for a specific video.

        Args:
            video_id: Video ID to retrieve

        Returns:
            Dictionary with video metadata or None if not found
        """
        session = self.Session()
        try:
            # Get all tasks related to this video
            tasks = session.query(Task).filter(Task.video_id == video_id).all()

            if not tasks:
                return None

            # Build comprehensive metadata from all tasks
            video_data = {
                "video_id": video_id,
                "tasks": [task.to_dict() for task in tasks],
                "plates": [],
                "gps_timeline": [],
                "summary": {}
            }

            # Extract plate information from heavy processing outputs
            for task in tasks:
                if task.task_type == "HEAVY_PROCESS_VIDEO" and task.outputs:
                    for output in task.outputs:
                        if isinstance(output, dict) and output.get("type") == "plates":
                            video_data["plates"].extend(output.get("data", []))

            # Extract GPS timeline from metadata
            for task in tasks:
                if task.metadata and task.metadata.get("gps_timeline"):
                    video_data["gps_timeline"] = task.metadata["gps_timeline"]

            # Calculate summary statistics
            plate_count = len(video_data["plates"])
            gps_points = len(video_data["gps_timeline"])

            video_data["summary"] = {
                "total_plates": plate_count,
                "unique_plates": len(set(p.get("plate_text") for p in video_data["plates"])),
                "gps_points": gps_points,
                "task_count": len(tasks),
                "completion_status": self._get_completion_status(tasks)
            }

            return video_data

        except Exception as e:
            logger.error(f"Error getting video metadata for {video_id}: {e}")
            raise
        finally:
            session.close()

    def list_videos(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        date_range: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        List videos with pagination and filtering.

        Args:
            limit: Maximum number of results to return
            offset: Offset for pagination
            sort_by: Field to sort by (created_at, video_id, etc.)
            sort_order: Sort order (asc or desc)
            date_range: Optional date range filter {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

        Returns:
            Dictionary with results and pagination info
        """
        session = self.Session()
        try:
            # Base query - get tasks that are complete and have video_id
            query = session.query(Task.task_id, Task.video_id, Task.created_at, Task.completed_at).filter(
                Task.state == "complete",
                Task.video_id.isnot(None)
            )

            # Apply date range filter if provided
            if date_range:
                start_date = date_range.get("start")
                end_date = date_range.get("end")

                if start_date:
                    query = query.filter(Task.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))

                if end_date:
                    query = query.filter(Task.created_at <= datetime.strptime(end_date + " 23:59:59", "%Y-%m-%d %H:%M:%S"))

            # Apply sorting
            if sort_by == "created_at":
                column = Task.created_at
            elif sort_by == "completed_at":
                column = Task.completed_at
            else:
                column = Task.video_id

            query = query.order_by(
                desc(column) if sort_order.lower() == "desc" else asc(column)
            )

            # Get total count for pagination
            total_count = query.count()

            # Apply limit and offset
            query = query.limit(limit).offset(offset)

            # Execute query
            results = query.all()

            videos = []
            for task_id, video_id, created_at, completed_at in results:
                videos.append({
                    "video_id": video_id,
                    "created_at": created_at.isoformat(),
                    "completed_at": completed_at.isoformat() if completed_at else None,
                    "task_count": 1  # Will be updated below
                })

            # Group by video_id and count tasks
            video_dict = {}
            for v in videos:
                if v["video_id"] not in video_dict:
                    video_dict[v["video_id"]] = {
                        "video_id": v["video_id"],
                        "created_at": v["created_at"],
                        "completed_at": v["completed_at"],
                        "task_count": 0
                    }
                video_dict[v["video_id"]]["task_count"] += 1

            videos = list(video_dict.values())

            return {
                "videos": videos,
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }

        except Exception as e:
            logger.error(f"Error listing videos: {e}")
            raise
        finally:
            session.close()

    def search_plates(
        self,
        plate_text: Optional[str] = None,
        confidence_min: Optional[float] = None,
        video_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for plates with filtering options.

        Args:
            plate_text: Partial or full plate text to search for (case-insensitive)
            confidence_min: Minimum confidence threshold (0.0-1.0)
            video_id: Optional video ID filter
            limit: Maximum number of results

        Returns:
            List of plate records matching criteria
        """
        session = self.Session()
        try:
            # Query all complete heavy processing tasks
            query = session.query(Task).filter(
                Task.task_type == "HEAVY_PROCESS_VIDEO",
                Task.state == "complete"
            )

            if video_id:
                query = query.filter(Task.video_id == video_id)

            tasks = query.limit(limit).all()

            results = []
            for task in tasks:
                # Extract plate data from outputs
                if task.outputs:
                    for output in task.outputs:
                        if isinstance(output, dict) and output.get("type") == "plates":
                            plates_data = output.get("data", [])

                            for plate in plates_data:
                                plate_record = {
                                    "video_id": task.video_id,
                                    "task_id": task.task_id,
                                    "plate_text": plate.get("text"),
                                    "confidence": plate.get("confidence"),
                                    "frame_number": plate.get("frame"),
                                    "timestamp": plate.get("timestamp"),
                                    "coordinates": plate.get("coordinates"),
                                    "crop_path": plate.get("crop_path")
                                }

                                # Apply filters
                                if plate_text:
                                    if plate_text.lower() not in plate_record["plate_text"].lower():
                                        continue

                                if confidence_min is not None:
                                    if plate_record["confidence"] < confidence_min:
                                        continue

                                results.append(plate_record)

            return results

        except Exception as e:
            logger.error(f"Error searching plates: {e}")
            raise
        finally:
            session.close()

    def get_gps_timeline(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Get GPS timeline for a specific video.

        Args:
            video_id: Video ID to retrieve GPS data for

        Returns:
            List of GPS points with timestamps
        """
        session = self.Session()
        try:
            # Find the heavy processing task for this video
            task = session.query(Task).filter(
                Task.video_id == video_id,
                Task.task_type == "HEAVY_PROCESS_VIDEO",
                Task.state == "complete"
            ).first()

            if not task or not task.metadata:
                return []

            return task.metadata.get("gps_timeline", [])

        except Exception as e:
            logger.error(f"Error getting GPS timeline for {video_id}: {e}")
            raise
        finally:
            session.close()

    def get_media_location(self, video_id: str) -> Optional[str]:
        """
        Get the filesystem location of archived media for a video.

        Args:
            video_id: Video ID to find

        Returns:
            Filesystem path or None if not found
        """
        try:
            config = self.config_loader.get_config()
            storage_paths = config.get("storage_paths", {}).get("shed_nas", {})

            if not storage_paths:
                return None

            archive_base = storage_paths.get("archive_base")
            if not archive_base:
                return None

            # Construct path based on configuration
            return f"{archive_base}/{video_id}/"

        except Exception as e:
            logger.error(f"Error getting media location for {video_id}: {e}")
            raise

    def get_plate_crop_path(self, video_id: str, plate_id: str) -> Optional[str]:
        """
        Get the path to a specific plate crop image.

        Args:
            video_id: Video ID
            plate_id: Plate identifier

        Returns:
            Full path to the crop image or None if not found
        """
        try:
            media_base = self.get_media_location(video_id)
            if not media_base:
                return None

            # Standard path format for plate crops
            return f"{media_base}plates/{plate_id}_crop.jpg"

        except Exception as e:
            logger.error(f"Error getting plate crop path for {video_id}/{plate_id}: {e}")
            raise

    def _get_completion_status(self, tasks: List[Task]) -> str:
        """
        Determine overall completion status based on task states.

        Args:
            tasks: List of Task objects

        Returns:
            Completion status string
        """
        if not tasks:
            return "not_started"

        complete_count = sum(1 for t in tasks if t.state == "complete")
        total_count = len(tasks)

        if complete_count == total_count:
            return "fully_completed"
        elif complete_count > 0:
            return "partially_completed"
        else:
            return "not_started"

    def get_video_summary(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a concise summary of video processing status.

        Args:
            video_id: Video ID

        Returns:
            Summary dictionary or None if video not found
        """
        session = self.Session()
        try:
            # Get all tasks for this video
            tasks = session.query(Task).filter(Task.video_id == video_id).all()

            if not tasks:
                return None

            plate_count = 0
            gps_points = 0

            # Count plates and GPS points from heavy processing task
            for task in tasks:
                if task.task_type == "HEAVY_PROCESS_VIDEO":
                    if task.outputs:
                        for output in task.outputs:
                            if isinstance(output, dict) and output.get("type") == "plates":
                                plate_count = len(output.get("data", []))

                    if task.metadata and task.metadata.get("gps_timeline"):
                        gps_points = len(task.metadata["gps_timeline"])

            return {
                "video_id": video_id,
                "plate_count": plate_count,
                "unique_plates": 0,  # Would need to analyze plates to count unique
                "gps_points": gps_points,
                "task_count": len(tasks),
                "status": self._get_completion_status(tasks)
            }

        except Exception as e:
            logger.error(f"Error getting video summary for {video_id}: {e}")
            raise
        finally:
            session.close()