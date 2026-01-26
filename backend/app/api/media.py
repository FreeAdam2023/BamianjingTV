"""Media API endpoints - thumbnails and waveforms."""

import subprocess
import time
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from app.api.timelines import (
    _get_manager,
    _get_thumbnail_worker,
    _get_waveform_worker,
    _get_jobs_dir,
)

router = APIRouter(prefix="/timelines", tags=["media"])


class CoverFrameResponse(BaseModel):
    """Response for cover frame capture."""
    timeline_id: str
    timestamp: float
    url: str
    message: str


class TitleCandidate(BaseModel):
    """A single title candidate."""
    index: int
    main: str
    sub: str
    style: str


class TitleCandidatesRequest(BaseModel):
    """Request for title generation."""
    instruction: str | None = None  # User instruction to guide AI


class TitleCandidatesResponse(BaseModel):
    """Response for title candidates."""
    timeline_id: str
    candidates: List[TitleCandidate]
    message: str


class ThumbnailGenerateRequest(BaseModel):
    """Request for thumbnail generation."""
    timestamp: float | None = None  # Custom timestamp (optional)
    use_cover_frame: bool = True  # Use previously captured cover frame
    main_title: str | None = None  # User-selected or custom main title
    sub_title: str | None = None  # User-selected or custom sub title


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


@router.post("/{timeline_id}/titles/generate", response_model=TitleCandidatesResponse)
async def generate_title_candidates(
    timeline_id: str,
    request: TitleCandidatesRequest | None = None,
    num_candidates: int = Query(default=5, ge=1, le=10, description="Number of candidates"),
):
    """Generate multiple title candidates for thumbnail.

    Args:
        timeline_id: Timeline ID
        request: Optional user instruction to guide AI
        num_candidates: Number of candidates to generate (1-10)

    Returns candidate titles for user selection.
    """
    from loguru import logger

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    thumbnail_worker = _get_thumbnail_worker()

    # Extract subtitles for analysis
    subtitles = [
        {"start": seg.start, "end": seg.end, "en": seg.en}
        for seg in timeline.segments if seg.en
    ]

    instruction = request.instruction if request else None

    try:
        candidates = await thumbnail_worker.generate_title_candidates(
            title=timeline.source_title,
            subtitles=subtitles,
            num_candidates=num_candidates,
            user_instruction=instruction,
        )

        response_candidates = [
            TitleCandidate(
                index=c["index"],
                main=c["main"],
                sub=c["sub"],
                style=c.get("style", ""),
            )
            for c in candidates
        ]

        logger.info(f"Generated {len(candidates)} title candidates for timeline {timeline_id}")

        return TitleCandidatesResponse(
            timeline_id=timeline_id,
            candidates=response_candidates,
            message=f"Generated {len(candidates)} title candidates",
        )

    except Exception as e:
        logger.exception(f"Title generation failed for timeline {timeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{timeline_id}/cover/capture", response_model=CoverFrameResponse)
async def capture_cover_frame(
    timeline_id: str,
    timestamp: float = Query(..., description="Timestamp in seconds to capture"),
):
    """Capture a frame at the specified timestamp as cover material.

    This frame will be used as the base for thumbnail generation.
    Overwrites any previously captured cover frame.
    """
    from loguru import logger

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    jobs_dir = _get_jobs_dir()
    if jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    job_dir = jobs_dir / timeline.job_id
    video_path = job_dir / "source" / "video.mp4"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    # Validate timestamp
    if timestamp < 0 or timestamp > timeline.source_duration:
        raise HTTPException(
            status_code=400,
            detail=f"Timestamp must be between 0 and {timeline.source_duration}"
        )

    # Create output directory
    output_dir = job_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract frame using ffmpeg
    cover_path = output_dir / "cover_frame.jpg"

    try:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-frames:v", "1",
            "-q:v", "2",
            str(cover_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        if not cover_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Failed to extract frame from video"
            )

        cover_url = f"/jobs/{timeline.job_id}/cover"

        logger.info(f"Captured cover frame for timeline {timeline_id} at {timestamp}s")

        return CoverFrameResponse(
            timeline_id=timeline_id,
            timestamp=timestamp,
            url=cover_url,
            message=f"Cover frame captured at {timestamp:.1f}s",
        )

    except subprocess.CalledProcessError as e:
        logger.exception(f"FFmpeg failed for timeline {timeline_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to extract frame")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Cover frame capture failed for timeline {timeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{timeline_id}/thumbnail", response_model=ThumbnailResponse)
async def generate_thumbnail(
    timeline_id: str,
    request: ThumbnailGenerateRequest | None = None,
):
    """Generate a YouTube-style thumbnail for the timeline.

    Usage modes:
    1. Default (use_cover_frame=True): Uses previously captured cover frame
    2. Custom timestamp: Extract frame at specific timestamp
    3. Auto mode: AI analyzes subtitles for best moment

    The thumbnail will have large Chinese clickbait text overlays.
    Call this endpoint multiple times to regenerate if not satisfied.
    """
    from loguru import logger

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    jobs_dir = _get_jobs_dir()
    if jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    thumbnail_worker = _get_thumbnail_worker()
    job_dir = jobs_dir / timeline.job_id
    video_path = job_dir / "source" / "video.mp4"
    output_dir = job_dir / "output"

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    # Extract subtitles for title generation
    subtitles = [
        {"start": seg.start, "end": seg.end, "en": seg.en}
        for seg in timeline.segments if seg.en
    ]

    # Determine frame source
    timestamp = None
    frame_path = None
    use_cover = request.use_cover_frame if request else True

    # Get user-provided titles if any
    main_title = request.main_title if request else None
    sub_title = request.sub_title if request else None

    if request and request.timestamp is not None:
        # Explicit timestamp provided
        timestamp = request.timestamp
        logger.info(f"Using custom timestamp: {timestamp}s")
    elif use_cover:
        # Try to use cover frame
        cover_path = output_dir / "cover_frame.jpg"
        if cover_path.exists():
            frame_path = cover_path
            logger.info(f"Using cover frame: {frame_path}")

    if main_title:
        logger.info(f"Using user-provided titles: {main_title} / {sub_title}")

    # Generate thumbnail
    filename = f"thumbnail_{int(time.time())}.png"

    try:
        if frame_path:
            # Generate from existing frame (cover frame)
            thumbnail_path = await thumbnail_worker.generate_from_frame(
                title=timeline.source_title,
                subtitles=subtitles,
                frame_path=frame_path,
                output_dir=output_dir,
                filename=filename,
                main_title=main_title,
                sub_title=sub_title,
            )
        else:
            # Generate from video with optional timestamp
            thumbnail_path = await thumbnail_worker.generate_for_timeline(
                title=timeline.source_title,
                subtitles=subtitles,
                video_path=video_path,
                output_dir=output_dir,
                filename=filename,
                timestamp=timestamp,
                main_title=main_title,
                sub_title=sub_title,
            )

        if not thumbnail_path:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate thumbnail. Check if LLM API is configured."
            )

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

    jobs_dir = _get_jobs_dir()
    if jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    waveform_worker = _get_waveform_worker()
    job_dir = jobs_dir / timeline.job_id
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

    jobs_dir = _get_jobs_dir()
    if jobs_dir is None:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    waveform_worker = _get_waveform_worker()
    job_dir = jobs_dir / timeline.job_id

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
