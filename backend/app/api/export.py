"""Export API endpoints for video rendering."""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.models.timeline import TimelineExportRequest
from app.api.timelines import (
    _get_manager,
    _get_export_worker,
    _get_youtube_worker,
    _jobs_dir,
)

router = APIRouter(prefix="/timelines", tags=["export"])


class ExportResponse(BaseModel):
    """Response for export request."""
    timeline_id: str
    status: str
    message: str


class ExportResultResponse(BaseModel):
    """Response with export result paths."""
    timeline_id: str
    full_video_path: Optional[str] = None
    essence_video_path: Optional[str] = None


@router.post("/{timeline_id}/export", response_model=ExportResponse)
async def trigger_export(
    timeline_id: str,
    request: TimelineExportRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger video export with bilingual subtitles.

    This starts a background task to export the video.
    Use GET /timelines/{id} to check export status and output paths.
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Update export settings
    manager.set_export_profile(
        timeline_id, request.profile, request.use_traditional_chinese
    )

    # Get video path from job
    if _jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    job_dir = _jobs_dir / timeline.job_id
    video_path = job_dir / "source" / "video.mp4"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    # Start background export task
    background_tasks.add_task(
        _run_export,
        timeline_id=timeline_id,
        video_path=video_path,
        output_dir=job_dir / "output",
        upload_to_youtube=request.upload_to_youtube,
        youtube_title=request.youtube_title,
        youtube_description=request.youtube_description,
        youtube_tags=request.youtube_tags,
        youtube_privacy=request.youtube_privacy,
    )

    message = f"Export started with profile: {request.profile.value}"
    if request.upload_to_youtube:
        message += " + YouTube upload"

    return ExportResponse(
        timeline_id=timeline_id,
        status="started",
        message=message,
    )


async def _run_export(
    timeline_id: str,
    video_path: Path,
    output_dir: Path,
    upload_to_youtube: bool = False,
    youtube_title: Optional[str] = None,
    youtube_description: Optional[str] = None,
    youtube_tags: Optional[List[str]] = None,
    youtube_privacy: str = "private",
) -> None:
    """Background task to run video export and optional YouTube upload."""
    from loguru import logger

    manager = _get_manager()
    export_worker = _get_export_worker()

    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        return

    try:
        # Step 1: Export video with subtitles
        full_path, essence_path = await export_worker.export(
            timeline=timeline,
            video_path=video_path,
            output_dir=output_dir,
        )

        # Update timeline with output paths
        manager.set_output_paths(
            timeline_id,
            full_path=str(full_path) if full_path else None,
            essence_path=str(essence_path) if essence_path else None,
        )

        logger.info(f"Export completed for timeline {timeline_id}")

        # Step 2: Upload to YouTube if requested
        if upload_to_youtube and full_path:
            youtube_worker = _get_youtube_worker()

            # Prepare title and description
            title = youtube_title or timeline.source_title
            description = youtube_description or f"Original: {timeline.source_url}"
            tags = youtube_tags or []

            logger.info(f"Uploading to YouTube: {title}")

            try:
                upload_result = await youtube_worker.upload(
                    video_path=full_path,
                    title=title,
                    description=description,
                    tags=tags,
                    privacy_status=youtube_privacy,
                )

                # Update timeline with YouTube info
                manager.set_youtube_info(
                    timeline_id,
                    video_id=upload_result["video_id"],
                    url=upload_result["url"],
                )

                logger.info(f"YouTube upload completed: {upload_result['url']}")

            except Exception as yt_err:
                logger.exception(f"YouTube upload failed for timeline {timeline_id}: {yt_err}")

    except Exception as e:
        logger.exception(f"Export failed for timeline {timeline_id}: {e}")
