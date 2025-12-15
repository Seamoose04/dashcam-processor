"""REST API endpoints for WebUI - provides data access for the web interface."""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Dict, Optional

from services.data_access import DataAccessLayer
from config.loader import ConfigurationLoader

router = APIRouter(prefix="/api/v1/webui", tags=["webui"])

# Dependency to get data access layer instance
def get_data_access() -> DataAccessLayer:
    """Get DataAccessLayer instance for WebUI endpoints."""
    try:
        config_loader = ConfigurationLoader()
        yield DataAccessLayer(config_loader=config_loader)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize data access: {str(e)}")

@router.get("/videos", response_model=Dict[str, List[dict]])
async def list_videos(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    start_date: Optional[str] = Query(None, description="Filter videos created on or after this date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter videos created before this date (YYYY-MM-DD)"),
    data_access: DataAccessLayer = Depends(get_data_access)
) -> Dict[str, List[dict]]:
    """
    List all processed videos with pagination and filtering.

    Args:
        limit: Maximum number of results to return
        offset: Offset for pagination
        sort_by: Field to sort by (created_at, completed_at, video_id)
        sort_order: Sort order (asc or desc)
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        Dictionary with videos list and pagination info
    """
    try:
        date_range = None
        if start_date or end_date:
            date_range = {}
            if start_date:
                date_range["start"] = start_date
            if end_date:
                date_range["end"] = end_date

        result = data_access.list_videos(
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            date_range=date_range
        )

        return {
            "videos": result["videos"],
            "total_count": result["total_count"],
            "limit": result["limit"],
            "offset": result["offset"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/{video_id}", response_model=dict)
async def get_video(
    video_id: str,
    data_access: DataAccessLayer = Depends(get_data_access)
) -> dict:
    """
    Get complete metadata for a specific video.

    Args:
        video_id: Video ID to retrieve

    Returns:
        Dictionary with comprehensive video metadata including plates, GPS timeline, etc.

    Raises:
        HTTPException 404: If video not found
    """
    try:
        video_data = data_access.get_video_metadata(video_id)
        if not video_data:
            raise HTTPException(status_code=404, detail="Video not found")

        return video_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/{video_id}/summary", response_model=dict)
async def get_video_summary(
    video_id: str,
    data_access: DataAccessLayer = Depends(get_data_access)
) -> dict:
    """
    Get a concise summary of video processing status.

    Args:
        video_id: Video ID to retrieve

    Returns:
        Summary dictionary with plate count, GPS points, etc.

    Raises:
        HTTPException 404: If video not found
    """
    try:
        summary = data_access.get_video_summary(video_id)
        if not summary:
            raise HTTPException(status_code=404, detail="Video not found")

        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/videos/{video_id}/gps", response_model=List[dict])
async def get_gps_timeline(
    video_id: str,
    data_access: DataAccessLayer = Depends(get_data_access)
) -> List[dict]:
    """
    Get GPS timeline for a specific video.

    Args:
        video_id: Video ID to retrieve GPS data for

    Returns:
        List of GPS points with timestamps and coordinates
    """
    try:
        gps_data = data_access.get_gps_timeline(video_id)
        return gps_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/plates", response_model=List[dict])
async def search_plates(
    plate_text: Optional[str] = Query(None, description="Partial or full plate text to search for"),
    confidence_min: Optional[float] = Query(None, ge=0, le=1.0, description="Minimum confidence threshold (0.0-1.0)"),
    video_id: Optional[str] = Query(None, description="Filter by specific video ID"),
    limit: int = Query(100, ge=1, le=500),
    data_access: DataAccessLayer = Depends(get_data_access)
) -> List[dict]:
    """
    Search for plates with filtering options.

    Args:
        plate_text: Partial or full plate text to search for (case-insensitive)
        confidence_min: Minimum confidence threshold
        video_id: Optional video ID filter
        limit: Maximum number of results

    Returns:
        List of plate records matching criteria
    """
    try:
        plates = data_access.search_plates(
            plate_text=plate_text,
            confidence_min=confidence_min,
            video_id=video_id,
            limit=limit
        )
        return plates
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/media/{video_id}/location", response_model=str)
async def get_media_location(
    video_id: str,
    data_access: DataAccessLayer = Depends(get_data_access)
) -> str:
    """
    Get the filesystem location of archived media for a video.

    Args:
        video_id: Video ID to find

    Returns:
        Filesystem path to the video's archive directory
    """
    try:
        location = data_access.get_media_location(video_id)
        if not location:
            raise HTTPException(status_code=404, detail="Media location not configured")

        return location
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/media/{video_id}/plates/{plate_id}", response_model=str)
async def get_plate_crop_path(
    video_id: str,
    plate_id: str,
    data_access: DataAccessLayer = Depends(get_data_access)
) -> str:
    """
    Get the path to a specific plate crop image.

    Args:
        video_id: Video ID
        plate_id: Plate identifier

    Returns:
        Full filesystem path to the crop image
    """
    try:
        path = data_access.get_plate_crop_path(video_id, plate_id)
        if not path:
            raise HTTPException(status_code=404, detail="Plate crop not found")

        return path
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))