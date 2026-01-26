"""Timeline API routes for review UI."""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from app.models.timeline import (
    EditableSegment,
    ExportProfile,
    SegmentBatchUpdate,
    SegmentState,
    SegmentUpdate,
    Timeline,
    TimelineExportRequest,
    TimelineSummary,
)
from app.services.timeline_manager import TimelineManager
from app.workers.export import ExportWorker
from app.workers.youtube import YouTubeWorker
from app.workers.thumbnail import ThumbnailWorker
from app.workers.waveform import WaveformWorker

router = APIRouter(prefix="/timelines", tags=["timelines"])

# Module-level manager (set at startup)
_timeline_manager: Optional[TimelineManager] = None
_export_worker: Optional[ExportWorker] = None
_youtube_worker: Optional[YouTubeWorker] = None
_thumbnail_worker: Optional[ThumbnailWorker] = None
_waveform_worker: Optional[WaveformWorker] = None
_jobs_dir: Optional[Path] = None


def set_timeline_manager(manager: TimelineManager) -> None:
    """Set the timeline manager instance."""
    global _timeline_manager
    _timeline_manager = manager


def set_export_worker(worker: ExportWorker) -> None:
    """Set the export worker instance."""
    global _export_worker
    _export_worker = worker


def set_youtube_worker(worker: YouTubeWorker) -> None:
    """Set the YouTube worker instance."""
    global _youtube_worker
    _youtube_worker = worker


def set_jobs_dir(jobs_dir: Path) -> None:
    """Set the jobs directory."""
    global _jobs_dir
    _jobs_dir = jobs_dir


def set_thumbnail_worker(worker: ThumbnailWorker) -> None:
    """Set the thumbnail worker instance."""
    global _thumbnail_worker
    _thumbnail_worker = worker


def set_waveform_worker(worker: WaveformWorker) -> None:
    """Set the waveform worker instance."""
    global _waveform_worker
    _waveform_worker = worker


def _get_manager() -> TimelineManager:
    """Get the timeline manager instance."""
    if _timeline_manager is None:
        raise RuntimeError("TimelineManager not initialized")
    return _timeline_manager


def _get_export_worker() -> ExportWorker:
    """Get the export worker instance."""
    if _export_worker is None:
        raise RuntimeError("ExportWorker not initialized")
    return _export_worker


def _get_youtube_worker() -> YouTubeWorker:
    """Get the YouTube worker instance."""
    if _youtube_worker is None:
        raise RuntimeError("YouTubeWorker not initialized")
    return _youtube_worker


def _get_thumbnail_worker() -> ThumbnailWorker:
    """Get the thumbnail worker instance."""
    if _thumbnail_worker is None:
        raise RuntimeError("ThumbnailWorker not initialized")
    return _thumbnail_worker


def _get_waveform_worker() -> WaveformWorker:
    """Get the waveform worker instance."""
    if _waveform_worker is None:
        raise RuntimeError("WaveformWorker not initialized")
    return _waveform_worker


# ============ Response Models ============


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


class ThumbnailResponse(BaseModel):
    """Response for thumbnail generation."""

    timeline_id: str
    thumbnail_url: str
    message: str


class WaveformResponse(BaseModel):
    """Response for waveform data."""

    peaks: List[float]
    sample_rate: int
    duration: float
    cached: bool = False
    track_type: str = "original"


class WaveformGenerateResponse(BaseModel):
    """Response for waveform generation request."""

    timeline_id: str
    track_type: str
    status: str
    message: str


# ============ Endpoints ============


@router.get("", response_model=List[TimelineSummary])
async def list_timelines(
    reviewed_only: bool = Query(default=False, description="Only reviewed timelines"),
    unreviewed_only: bool = Query(
        default=False, description="Only unreviewed timelines"
    ),
    limit: int = Query(default=100, le=500, description="Maximum results"),
):
    """List all timelines with optional filtering."""
    manager = _get_manager()
    return manager.list_timelines(
        reviewed_only=reviewed_only,
        unreviewed_only=unreviewed_only,
        limit=limit,
    )


@router.get("/stats")
async def get_timeline_stats():
    """Get timeline statistics."""
    manager = _get_manager()
    return manager.get_stats()


@router.get("/by-job/{job_id}", response_model=Timeline)
async def get_timeline_by_job(job_id: str):
    """Get timeline by job ID."""
    manager = _get_manager()
    timeline = manager.get_timeline_by_job(job_id)
    if not timeline:
        raise HTTPException(
            status_code=404, detail=f"No timeline found for job {job_id}"
        )
    return timeline


@router.get("/{timeline_id}", response_model=Timeline)
async def get_timeline(timeline_id: str):
    """Get a specific timeline with all segments."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    return timeline


@router.delete("/{timeline_id}")
async def delete_timeline(timeline_id: str):
    """Delete a timeline."""
    manager = _get_manager()
    if not manager.delete_timeline(timeline_id):
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {"message": f"Timeline {timeline_id} deleted"}


@router.patch("/{timeline_id}/segments/{segment_id}", response_model=EditableSegment)
async def update_segment(
    timeline_id: str,
    segment_id: int,
    update: SegmentUpdate,
):
    """Update a single segment (state, trim, text)."""
    manager = _get_manager()
    segment = manager.update_segment(timeline_id, segment_id, update)
    if not segment:
        raise HTTPException(status_code=404, detail="Timeline or segment not found")
    return segment


@router.post("/{timeline_id}/segments/batch")
async def batch_update_segments(
    timeline_id: str,
    batch: SegmentBatchUpdate,
):
    """Batch update multiple segments with the same state."""
    manager = _get_manager()
    updated = manager.batch_update_segments(
        timeline_id, batch.segment_ids, batch.state
    )
    if updated == 0:
        raise HTTPException(
            status_code=404, detail="Timeline not found or no segments matched"
        )
    return {"updated": updated, "state": batch.state.value}


@router.post("/{timeline_id}/mark-reviewed")
async def mark_timeline_reviewed(timeline_id: str):
    """Mark a timeline as reviewed."""
    manager = _get_manager()
    if not manager.mark_reviewed(timeline_id):
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {"message": f"Timeline {timeline_id} marked as reviewed"}


@router.post("/{timeline_id}/segments/keep-all")
async def keep_all_segments(timeline_id: str):
    """Mark all segments as KEEP."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    segment_ids = [seg.id for seg in timeline.segments]
    updated = manager.batch_update_segments(timeline_id, segment_ids, SegmentState.KEEP)
    return {"updated": updated, "state": "keep"}


@router.post("/{timeline_id}/segments/drop-all")
async def drop_all_segments(timeline_id: str):
    """Mark all segments as DROP."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    segment_ids = [seg.id for seg in timeline.segments]
    updated = manager.batch_update_segments(timeline_id, segment_ids, SegmentState.DROP)
    return {"updated": updated, "state": "drop"}


@router.post("/{timeline_id}/segments/reset-all")
async def reset_all_segments(timeline_id: str):
    """Reset all segments to UNDECIDED."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    segment_ids = [seg.id for seg in timeline.segments]
    updated = manager.batch_update_segments(
        timeline_id, segment_ids, SegmentState.UNDECIDED
    )
    return {"updated": updated, "state": "undecided"}


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


@router.post("/{timeline_id}/thumbnail", response_model=ThumbnailResponse)
async def generate_thumbnail(timeline_id: str):
    """Generate a YouTube-style thumbnail for the timeline.

    Uses AI to analyze the video content and generate an eye-catching thumbnail.
    Call this endpoint multiple times to regenerate if not satisfied.
    """
    from loguru import logger
    import time

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if _jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    thumbnail_worker = _get_thumbnail_worker()

    # Extract English subtitles for content analysis
    subtitles = [seg.en for seg in timeline.segments if seg.en]

    # Generate thumbnail
    output_dir = _jobs_dir / timeline.job_id / "output"

    # Use timestamp for unique filename on regeneration
    filename = f"thumbnail_{int(time.time())}.png"

    try:
        thumbnail_path = await thumbnail_worker.generate_for_timeline(
            title=timeline.source_title,
            subtitles=subtitles,
            output_dir=output_dir,
            filename=filename,
        )

        if not thumbnail_path:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate thumbnail. Check if image API is configured."
            )

        # Return URL that can be served
        thumbnail_url = f"/api/jobs/{timeline.job_id}/thumbnail/{filename}"

        logger.info(f"Generated thumbnail for timeline {timeline_id}: {thumbnail_url}")

        return ThumbnailResponse(
            timeline_id=timeline_id,
            thumbnail_url=thumbnail_url,
            message="Thumbnail generated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Thumbnail generation failed for timeline {timeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{timeline_id}/waveform/{track_type}", response_model=WaveformResponse)
async def get_waveform(
    timeline_id: str,
    track_type: str = "original",
):
    """Get waveform peak data for a timeline's audio track.

    Args:
        timeline_id: Timeline ID
        track_type: Audio track type (original, dubbing, bgm)

    Returns cached waveform data if available, otherwise 404.
    Use POST /timelines/{id}/waveform/generate to generate if not available.
    """
    from loguru import logger

    if track_type not in ("original", "dubbing", "bgm"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid track type: {track_type}. Must be one of: original, dubbing, bgm"
        )

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if _jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    waveform_worker = _get_waveform_worker()
    job_dir = _jobs_dir / timeline.job_id
    peaks_path = job_dir / "waveforms" / f"{track_type}.json"

    # Try to load cached waveform
    waveform_data = await waveform_worker.load_peaks(peaks_path)

    if not waveform_data:
        raise HTTPException(
            status_code=404,
            detail=f"Waveform not found for track: {track_type}. Use POST to generate."
        )

    return WaveformResponse(
        peaks=waveform_data["peaks"],
        sample_rate=waveform_data["sample_rate"],
        duration=waveform_data["duration"],
        cached=True,
        track_type=track_type,
    )


@router.post("/{timeline_id}/waveform/generate", response_model=WaveformGenerateResponse)
async def generate_waveform(
    timeline_id: str,
    track_type: str = Query(default="original", description="Audio track type"),
    background_tasks: BackgroundTasks = None,
):
    """Generate waveform peak data for a timeline's audio track.

    Args:
        timeline_id: Timeline ID
        track_type: Audio track type (original, dubbing, bgm)

    Generates waveform peaks from the audio file and caches them.
    For large files, this runs as a background task.
    """
    from loguru import logger

    if track_type not in ("original", "dubbing", "bgm"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid track type: {track_type}. Must be one of: original, dubbing, bgm"
        )

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if _jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    waveform_worker = _get_waveform_worker()
    job_dir = _jobs_dir / timeline.job_id

    try:
        # Generate waveform (this is relatively fast, so we do it synchronously)
        result = await waveform_worker.generate_for_job(job_dir, track_type)

        logger.info(f"Generated waveform for timeline {timeline_id}, track: {track_type}")

        return WaveformGenerateResponse(
            timeline_id=timeline_id,
            track_type=track_type,
            status="completed",
            message=f"Waveform generated: {result.get('total_samples', 0)} samples, "
                    f"{result.get('file_size_kb', 0):.1f} KB",
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Waveform generation failed for timeline {timeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
