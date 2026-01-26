"""Media API endpoints - thumbnails and waveforms."""

import time
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from app.api.timelines import (
    _get_manager,
    _get_thumbnail_worker,
    _get_waveform_worker,
    _jobs_dir,
)

router = APIRouter(prefix="/timelines", tags=["media"])


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


@router.post("/{timeline_id}/thumbnail", response_model=ThumbnailResponse)
async def generate_thumbnail(timeline_id: str):
    """Generate a YouTube-style thumbnail for the timeline.

    Extracts a frame from the video at the most dramatic moment (analyzed via subtitles),
    then adds Chinese clickbait text overlays.
    Call this endpoint multiple times to regenerate if not satisfied.
    """
    from loguru import logger

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if _jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    thumbnail_worker = _get_thumbnail_worker()

    # Get video path for frame extraction
    job_dir = _jobs_dir / timeline.job_id
    video_path = job_dir / "source" / "video.mp4"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    # Extract subtitles with timestamps for emotional moment analysis
    subtitles = [
        {"start": seg.start, "end": seg.end, "en": seg.en}
        for seg in timeline.segments if seg.en
    ]

    # Generate thumbnail
    output_dir = job_dir / "output"

    # Use timestamp for unique filename on regeneration
    filename = f"thumbnail_{int(time.time())}.png"

    try:
        thumbnail_path = await thumbnail_worker.generate_for_timeline(
            title=timeline.source_title,
            subtitles=subtitles,
            video_path=video_path,
            output_dir=output_dir,
            filename=filename,
        )

        if not thumbnail_path:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate thumbnail. Check if image API is configured."
            )

        # Return URL that can be served (without /api/ prefix for direct backend access)
        thumbnail_url = f"/jobs/{timeline.job_id}/thumbnail/{filename}"

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
