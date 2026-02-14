"""Export API endpoints for video rendering."""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.models.timeline import ExportStatus, SubtitleStyleMode, TimelineExportRequest
from app.models.job import JobStatus
from app.workers.export import ExportCancelledError
from app.api.timelines import (
    _get_manager,
    _get_export_worker,
    _get_youtube_worker,
    _get_jobs_dir,
)
from app.api.jobs import _get_job_manager

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


class ExportStatusResponse(BaseModel):
    """Response for export status check."""
    timeline_id: str
    status: ExportStatus
    progress: float
    message: Optional[str] = None
    error: Optional[str] = None
    youtube_url: Optional[str] = None
    full_video_path: Optional[str] = None
    essence_video_path: Optional[str] = None


@router.get("/{timeline_id}/export/status", response_model=ExportStatusResponse)
async def get_export_status(timeline_id: str):
    """Get current export status for a timeline.

    Use this endpoint to poll for export progress.
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    return ExportStatusResponse(
        timeline_id=timeline_id,
        status=timeline.export_status,
        progress=timeline.export_progress,
        message=timeline.export_message,
        error=timeline.export_error,
        youtube_url=timeline.youtube_url,
        full_video_path=timeline.output_full_path,
        essence_video_path=timeline.output_essence_path,
    )


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

    # Update subtitle style mode if specified in request
    if request.subtitle_style_mode is not None:
        timeline.subtitle_style_mode = request.subtitle_style_mode
        manager.save_timeline(timeline)

    # Update card panel visibility if specified in request
    if request.show_card_panel is not None:
        timeline.show_card_panel = request.show_card_panel
        manager.save_timeline(timeline)

    # Get video path from job
    jobs_dir = _get_jobs_dir()
    if jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    job_dir = jobs_dir / timeline.job_id
    video_path = job_dir / "source" / "video.mp4"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    # Start background export task
    background_tasks.add_task(
        _run_export,
        timeline_id=timeline_id,
        video_path=video_path,
        output_dir=job_dir / "output",
        subtitle_style=request.subtitle_style,
        upload_to_youtube=request.upload_to_youtube,
        youtube_title=request.youtube_title,
        youtube_description=request.youtube_description,
        youtube_tags=request.youtube_tags,
        youtube_privacy=request.youtube_privacy,
        test_seconds=request.test_seconds,
    )

    message = f"Export started with profile: {request.profile.value}"
    if request.upload_to_youtube:
        message += " + YouTube upload"

    return ExportResponse(
        timeline_id=timeline_id,
        status="started",
        message=message,
    )


@router.post("/{timeline_id}/export/cancel", response_model=ExportResponse)
async def cancel_export(timeline_id: str):
    """Cancel a running export for a timeline.

    Only works when export_status is EXPORTING or UPLOADING.
    Kills the active subprocess and resets status to IDLE.
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if timeline.export_status not in (ExportStatus.EXPORTING, ExportStatus.UPLOADING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel export: status is {timeline.export_status.value}",
        )

    # Set status to CANCELLING so background task detects it
    manager.update_export_status(
        timeline_id,
        status=ExportStatus.CANCELLING,
        progress=timeline.export_progress,
        message="正在取消...",
    )

    # Kill the active subprocess
    export_worker = _get_export_worker()
    await export_worker.cancel_export(timeline_id)

    return ExportResponse(
        timeline_id=timeline_id,
        status="cancelling",
        message="Export cancellation requested",
    )


async def _run_export(
    timeline_id: str,
    video_path: Path,
    output_dir: Path,
    subtitle_style=None,
    upload_to_youtube: bool = False,
    youtube_title: Optional[str] = None,
    youtube_description: Optional[str] = None,
    youtube_tags: Optional[List[str]] = None,
    youtube_privacy: str = "private",
    test_seconds: Optional[float] = None,
) -> None:
    """Background task to run video export and optional YouTube upload."""
    from loguru import logger

    manager = _get_manager()
    export_worker = _get_export_worker()
    job_manager = _get_job_manager()

    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        return

    # Apply test_seconds as in-memory override (not saved to timeline JSON)
    if test_seconds is not None and test_seconds > 0:
        trim_start = timeline.video_trim_start or 0.0
        timeline.video_trim_end = trim_start + test_seconds

    # Get job for timing tracking
    job = job_manager.get_job(timeline.job_id)

    try:
        # Initialize export status
        manager.update_export_status(
            timeline_id,
            status=ExportStatus.EXPORTING,
            progress=0.0,
            message="Preparing export...",
        )

        # Start export timing
        if job:
            job.start_step("export")
            job_manager.save_job(job)

        # Step 1: Export video with subtitles
        manager.update_export_status(
            timeline_id,
            status=ExportStatus.EXPORTING,
            progress=10.0,
            message="Generating subtitles...",
        )

        def on_render_progress(progress: float, message: str):
            """Callback to stream Remotion render progress with ETA to the UI."""
            manager.update_export_status(
                timeline_id,
                status=ExportStatus.EXPORTING,
                progress=progress,
                message=message,
            )

        full_path, essence_path = await export_worker.export(
            timeline=timeline,
            video_path=video_path,
            output_dir=output_dir,
            subtitle_style=subtitle_style,
            progress_callback=on_render_progress,
            timeline_id=timeline_id,
        )

        # Update timeline with output paths
        manager.set_output_paths(
            timeline_id,
            full_path=str(full_path) if full_path else None,
            essence_path=str(essence_path) if essence_path else None,
        )

        manager.update_export_status(
            timeline_id,
            status=ExportStatus.EXPORTING,
            progress=70.0,
            message="Video rendering complete",
        )

        logger.info(f"Export completed for timeline {timeline_id}")

        # Step 2: Upload to YouTube if requested
        if upload_to_youtube and full_path:
            youtube_worker = _get_youtube_worker()

            # Prepare title and description
            title = youtube_title or timeline.source_title
            description = youtube_description or f"Original: {timeline.source_url}"
            tags = youtube_tags or []

            manager.update_export_status(
                timeline_id,
                status=ExportStatus.UPLOADING,
                progress=75.0,
                message=f"Uploading to YouTube: {title[:50]}...",
            )

            logger.info(f"Uploading to YouTube: {title}")

            # Progress callback for YouTube upload (75% to 99%)
            def upload_progress_callback(upload_percent: int):
                # Map upload progress (0-100) to overall progress (75-99)
                overall_progress = 75.0 + (upload_percent * 0.24)
                manager.update_export_status(
                    timeline_id,
                    status=ExportStatus.UPLOADING,
                    progress=overall_progress,
                    message=f"Uploading to YouTube: {upload_percent}%",
                )

            try:
                upload_result = await youtube_worker.upload(
                    video_path=full_path,
                    title=title,
                    description=description,
                    tags=tags,
                    privacy_status=youtube_privacy,
                    progress_callback=upload_progress_callback,
                )

                # Update timeline with YouTube info
                manager.set_youtube_info(
                    timeline_id,
                    video_id=upload_result["video_id"],
                    url=upload_result["url"],
                )

                manager.update_export_status(
                    timeline_id,
                    status=ExportStatus.COMPLETED,
                    progress=100.0,
                    message=f"YouTube upload complete: {upload_result['url']}",
                )

                # Update job status to COMPLETED and end export timing
                if job:
                    job.end_step("export")
                    await job_manager.update_status(job, JobStatus.COMPLETED, progress=1.0)

                logger.info(f"YouTube upload completed: {upload_result['url']}")

            except Exception as yt_err:
                logger.exception(f"YouTube upload failed for timeline {timeline_id}: {yt_err}")
                manager.update_export_status(
                    timeline_id,
                    status=ExportStatus.FAILED,
                    progress=75.0,
                    message="YouTube upload failed",
                    error=str(yt_err),
                )
        else:
            # No YouTube upload, mark as completed
            manager.update_export_status(
                timeline_id,
                status=ExportStatus.COMPLETED,
                progress=100.0,
                message="Export complete",
            )

            # Update job status to COMPLETED and end export timing
            if job:
                job.end_step("export")
                await job_manager.update_status(job, JobStatus.COMPLETED, progress=1.0)

    except ExportCancelledError:
        logger.info(f"Export cancelled for timeline {timeline_id}")
        # Clean up partial output files
        for partial_file in output_dir.glob("*.mp4"):
            try:
                partial_file.unlink()
                logger.info(f"Cleaned up partial output: {partial_file}")
            except OSError:
                pass
        # Reset status back to IDLE
        manager.update_export_status(
            timeline_id,
            status=ExportStatus.IDLE,
            progress=0.0,
            message="导出已取消",
        )

    except Exception as e:
        logger.exception(f"Export failed for timeline {timeline_id}: {e}")
        manager.update_export_status(
            timeline_id,
            status=ExportStatus.FAILED,
            progress=0.0,
            message="Export failed",
            error=str(e),
        )


@router.get("/{timeline_id}/video/full")
async def get_export_video_full(timeline_id: str):
    """Stream the full exported video (with subtitles) for preview."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if not timeline.output_full_path:
        raise HTTPException(status_code=404, detail="Full video not exported yet. Complete export first.")

    video_path = Path(timeline.output_full_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Exported video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
    )


@router.get("/{timeline_id}/video/essence")
async def get_export_video_essence(timeline_id: str):
    """Stream the essence exported video (KEEP segments only) for preview."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if not timeline.output_essence_path:
        raise HTTPException(status_code=404, detail="Essence video not exported yet. Complete export first.")

    video_path = Path(timeline.output_essence_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Exported video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
    )
