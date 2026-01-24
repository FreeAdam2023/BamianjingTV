"""YouTube API endpoints."""

from pathlib import Path
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.workers.youtube import YouTubeWorker, YouTubeUploadError


router = APIRouter(prefix="/youtube", tags=["youtube"])

# Worker
youtube_worker = YouTubeWorker()


# ============ Request/Response Models ============

class UploadRequest(BaseModel):
    """Request for video upload."""
    video_path: str
    title: str
    description: str
    tags: List[str] = []
    category_id: str = "22"
    privacy_status: str = "private"
    thumbnail_path: Optional[str] = None
    schedule_hours: Optional[int] = None  # Hours to delay publishing
    made_for_kids: bool = False


class UpdateRequest(BaseModel):
    """Request for updating video metadata."""
    video_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy_status: Optional[str] = None


class UploadResponse(BaseModel):
    """Response for video upload."""
    success: bool
    video_id: str
    url: str
    status: str
    publish_at: Optional[str] = None


# ============ Endpoints ============

@router.post("/upload", response_model=UploadResponse)
async def upload_video(request: UploadRequest):
    """Upload video to YouTube."""
    try:
        # Calculate publish time if scheduling
        publish_at = None
        if request.schedule_hours:
            publish_at = youtube_worker.calculate_publish_time(
                delay_hours=request.schedule_hours,
            )

        result = await youtube_worker.upload(
            video_path=Path(request.video_path),
            title=request.title,
            description=request.description,
            tags=request.tags,
            category_id=request.category_id,
            privacy_status=request.privacy_status,
            thumbnail_path=Path(request.thumbnail_path) if request.thumbnail_path else None,
            publish_at=publish_at,
            made_for_kids=request.made_for_kids,
        )

        return UploadResponse(
            success=True,
            video_id=result["video_id"],
            url=result["url"],
            status=result["status"],
            publish_at=result.get("publish_at"),
        )

    except YouTubeUploadError as e:
        logger.error(f"YouTube upload failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/thumbnail/{video_id}")
async def set_thumbnail(video_id: str, thumbnail_path: str):
    """Set custom thumbnail for a video."""
    try:
        success = await youtube_worker.set_thumbnail(
            video_id=video_id,
            thumbnail_path=Path(thumbnail_path),
        )

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Failed to set thumbnail"
            )

        return {"success": True, "video_id": video_id}

    except Exception as e:
        logger.error(f"Set thumbnail failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/update")
async def update_video(request: UpdateRequest):
    """Update video metadata."""
    try:
        result = await youtube_worker.update_video(
            video_id=request.video_id,
            title=request.title,
            description=request.description,
            tags=request.tags,
            privacy_status=request.privacy_status,
        )

        return {
            "success": True,
            **result,
        }

    except YouTubeUploadError as e:
        logger.error(f"Update failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quota")
async def get_quota():
    """Get YouTube channel info and quota status."""
    try:
        quota = await youtube_worker.get_upload_quota()
        return {
            "success": True,
            **quota,
        }

    except YouTubeUploadError as e:
        logger.error(f"Quota check failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Quota check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/status")
async def auth_status():
    """Check YouTube authentication status."""
    try:
        # Try to get quota - this will fail if not authenticated
        await youtube_worker.get_upload_quota()
        return {
            "authenticated": True,
            "message": "YouTube API authenticated",
        }
    except YouTubeUploadError as e:
        return {
            "authenticated": False,
            "message": str(e),
        }
    except Exception as e:
        return {
            "authenticated": False,
            "message": f"Authentication error: {e}",
        }
