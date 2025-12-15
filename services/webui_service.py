"""WebUI Service - Main service for displaying processed video data to web interface."""

import logging
from typing import List, Dict, Optional, Any

from services.data_access import DataAccessLayer
from config.loader import ConfigurationLoader

logger = logging.getLogger(__name__)

class WebUIServer:
    """Main WebUI service that coordinates metadata retrieval and media access."""

    def __init__(self, data_access: DataAccessLayer = None, config_loader: ConfigurationLoader = None):
        """
        Initialize the WebUI service.

        Args:
            data_access: DataAccessLayer instance
            config_loader: ConfigurationLoader instance
        """
        self.config_loader = config_loader or ConfigurationLoader()
        self.data_access = data_access or DataAccessLayer(config_loader=self.config_loader)

    def get_video_browser_data(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """
        Get data for the video browser view.

        Args:
            limit: Maximum number of results
            offset: Pagination offset
            sort_by: Field to sort by
            sort_order: Sort order

        Returns:
            Dictionary with videos and pagination info
        """
        try:
            result = self.data_access.list_videos(
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order
            )

            # Enrich video data with summaries
            videos_with_summaries = []
            for video in result["videos"]:
                summary = self.data_access.get_video_summary(video["video_id"])
                if summary:
                    video_data = {
                        "video_id": video["video_id"],
                        "created_at": video["created_at"],
                        "completed_at": video["completed_at"],
                        "plate_count": summary.get("plate_count", 0),
                        "gps_points": summary.get("gps_points", 0),
                        "status": summary.get("status", "unknown"),
                        "task_count": summary.get("task_count", 1)
                    }
                    videos_with_summaries.append(video_data)

            result["videos"] = videos_with_summaries
            return result

        except Exception as e:
            logger.error(f"Error getting video browser data: {e}")
            raise

    def get_video_detail(
        self,
        video_id: str
    ) -> Dict[str, Any]:
        """
        Get complete detail for a specific video.

        Args:
            video_id: Video ID to retrieve

        Returns:
            Dictionary with comprehensive video details including plates, GPS, and media paths
        """
        try:
            # Get basic metadata
            video_metadata = self.data_access.get_video_metadata(video_id)
            if not video_metadata:
                raise ValueError(f"Video {video_id} not found")

            # Get GPS timeline
            gps_data = self.data_access.get_gps_timeline(video_id)

            # Get media location
            media_location = self.data_access.get_media_location(video_id)

            return {
                "metadata": video_metadata,
                "gps_timeline": gps_data,
                "media_location": media_location,
                "video_id": video_id
            }

        except Exception as e:
            logger.error(f"Error getting video detail for {video_id}: {e}")
            raise

    def search_plates_across_videos(
        self,
        plate_text: Optional[str] = None,
        confidence_min: Optional[float] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Search for plates across all videos with filtering.

        Args:
            plate_text: Partial or full plate text to search for
            confidence_min: Minimum confidence threshold
            limit: Maximum number of results

        Returns:
            List of plate records with video context
        """
        try:
            plates = self.data_access.search_plates(
                plate_text=plate_text,
                confidence_min=confidence_min,
                limit=limit
            )

            # Enrich with media paths if available
            for plate in plates:
                plate["media_path"] = None
                if "crop_path" in plate and plate["crop_path"]:
                    plate["media_path"] = self.data_access.get_plate_crop_path(
                        plate["video_id"],
                        plate["crop_path"]
                    )

            return plates

        except Exception as e:
            logger.error(f"Error searching plates: {e}")
            raise

    def get_map_view_data(
        self,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get data for map view - all plate sightings with GPS coordinates.

        Args:
            limit: Maximum number of plate sightings to return

        Returns:
            List of plate records with GPS data
        """
        try:
            # Search for plates (no filters)
            plates = self.data_access.search_plates(limit=limit)

            map_data = []
            for plate in plates:
                if plate.get("coordinates"):
                    map_data.append({
                        "video_id": plate["video_id"],
                        "plate_text": plate["plate_text"],
                        "confidence": plate["confidence"],
                        "timestamp": plate["timestamp"],
                        "latitude": plate["coordinates"].get("lat"),
                        "longitude": plate["coordinates"].get("lon"),
                        "frame_number": plate.get("frame_number")
                    })

            return map_data

        except Exception as e:
            logger.error(f"Error getting map view data: {e}")
            raise

    def get_timeline_data_for_video(
        self,
        video_id: str
    ) -> Dict[str, Any]:
        """
        Get timeline data for a specific video including plates and GPS.

        Args:
            video_id: Video ID to retrieve timeline for

        Returns:
            Dictionary with timeline data organized by time/frame
        """
        try:
            # Get video metadata
            video_metadata = self.data_access.get_video_metadata(video_id)
            if not video_metadata:
                raise ValueError(f"Video {video_id} not found")

            # Get GPS timeline
            gps_data = self.data_access.get_gps_timeline(video_id)

            # Organize plates by frame/timestamp
            plates_by_frame = {}
            for plate in video_metadata["plates"]:
                frame_num = plate.get("frame", 0)
                if frame_num not in plates_by_frame:
                    plates_by_frame[frame_num] = []
                plates_by_frame[frame_num].append(plate)

            timeline = []

            # Build timeline entries
            current_time = None

            for i, gps_point in enumerate(gps_data):
                timestamp = gps_point.get("timestamp")
                if timestamp:
                    current_time = timestamp

                frame_num = gps_point.get("frame", i)
                entry = {
                    "time": current_time,
                    "frame": frame_num,
                    "coordinates": gps_point.get("coordinates"),
                    "speed": gps_point.get("speed"),
                    "plates": plates_by_frame.get(frame_num, [])
                }

                timeline.append(entry)

            return {
                "video_id": video_id,
                "timeline": timeline,
                "total_plates": len(video_metadata["plates"]),
                "total_gps_points": len(gps_data)
            }

        except Exception as e:
            logger.error(f"Error getting timeline data for {video_id}: {e}")
            raise

    def get_recent_activity(
        self,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get recent processing activity for dashboard.

        Args:
            limit: Maximum number of videos to return

        Returns:
            Dictionary with recent videos and statistics
        """
        try:
            # Get most recently completed videos
            result = self.data_access.list_videos(
                limit=limit,
                sort_by="completed_at",
                sort_order="desc"
            )

            total_plates = 0
            total_gps_points = 0

            # Calculate aggregations
            for video in result["videos"]:
                summary = self.data_access.get_video_summary(video["video_id"])
                if summary:
                    total_plates += summary.get("plate_count", 0)
                    total_gps_points += summary.get("gps_points", 0)

            return {
                "recent_videos": result["videos"],
                "total_recent_videos": len(result["videos"]),
                "total_plates_found": total_plates,
                "total_gps_points": total_gps_points,
                "time_range": {
                    "start": min(v["completed_at"] for v in result["videos"]) if result["videos"] else None,
                    "end": max(v["completed_at"] for v in result["videos"]) if result["videos"] else None
                }
            }

        except Exception as e:
            logger.error(f"Error getting recent activity: {e}")
            raise

    def get_statistics_summary(self) -> Dict[str, Any]:
        """
        Get overall statistics about processed videos.

        Returns:
            Dictionary with summary statistics
        """
        try:
            # Get all videos (with large limit)
            result = self.data_access.list_videos(limit=1000)

            total_plates = 0
            unique_plate_texts = set()
            total_gps_points = 0

            # Sample some videos to get statistics
            sample_size = min(50, len(result["videos"]))
            sampled_videos = result["videos"][:sample_size]

            for video in sampled_videos:
                summary = self.data_access.get_video_summary(video["video_id"])
                if summary:
                    total_plates += summary.get("plate_count", 0)
                    total_gps_points += summary.get("gps_points", 0)

                    # Get plates to count unique ones
                    video_metadata = self.data_access.get_video_metadata(video["video_id"])
                    if video_metadata and video_metadata["plates"]:
                        for plate in video_metadata["plates"]:
                            text = plate.get("text")
                            if text:
                                unique_plate_texts.add(text)

            # Calculate averages (based on sample)
            avg_plates_per_video = total_plates / len(sampled_videos) if sampled_videos else 0
            avg_gps_points_per_video = total_gps_points / len(sampled_videos) if sampled_videos else 0

            return {
                "total_videos_processed": result["total_count"],
                "total_plates_found": total_plates,
                "unique_plate_texts_count": len(unique_plate_texts),
                "total_gps_points": total_gps_points,
                "average_plates_per_video": avg_plates_per_video,
                "average_gps_points_per_video": avg_gps_points_per_video,
                "completion_rate": self._calculate_completion_rate(result["videos"])
            }

        except Exception as e:
            logger.error(f"Error getting statistics summary: {e}")
            raise

    def _calculate_completion_rate(self, videos: List[Dict[str, Any]]) -> float:
        """
        Calculate completion rate based on video statuses.

        Args:
            videos: List of video dictionaries

        Returns:
            Completion rate as a percentage (0-100)
        """
        if not videos:
            return 0.0

        completed = sum(1 for v in videos if v.get("status") == "fully_completed")
        return (completed / len(videos)) * 100