"""Media API endpoints - thumbnails and waveforms."""

import time
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


class ThumbnailCandidate(BaseModel):
    """A single thumbnail candidate screenshot."""
    index: int
    timestamp: float
    filename: str
    url: str


class ThumbnailCandidatesResponse(BaseModel):
    """Response for thumbnail candidates."""
    timeline_id: str
    candidates: List[ThumbnailCandidate]
    duration: float
    message: str


class ThumbnailGenerateRequest(BaseModel):
    """Request for thumbnail generation."""
    timestamp: float | None = None  # Custom timestamp (optional)
    candidate_index: int | None = None  # Use candidate frame (optional)


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


@router.post("/{timeline_id}/thumbnail/candidates", response_model=ThumbnailCandidatesResponse)
async def generate_thumbnail_candidates(
    timeline_id: str,
    num_candidates: int = Query(default=6, ge=2, le=12, description="Number of candidates"),
):
    """Generate candidate screenshot images for thumbnail selection.

    Extracts frames at evenly distributed timestamps throughout the video.
    User can then select one to use as the base for final thumbnail generation.
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

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Source video not found")

    # Create candidates directory
    candidates_dir = job_dir / "output" / "thumbnail_candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)

    # Clean up old candidates
    for old_file in candidates_dir.glob("candidate_*.jpg"):
        try:
            old_file.unlink()
        except Exception:
            pass

    try:
        candidates = thumbnail_worker.extract_candidate_frames(
            video_path=video_path,
            output_dir=candidates_dir,
            num_candidates=num_candidates,
            duration=timeline.source_duration,
        )

        if not candidates:
            raise HTTPException(
                status_code=500,
                detail="Failed to extract candidate frames from video"
            )

        # Convert to response format with URLs
        response_candidates = [
            ThumbnailCandidate(
                index=c["index"],
                timestamp=c["timestamp"],
                filename=c["filename"],
                url=f"/jobs/{timeline.job_id}/thumbnail/candidates/{c['filename']}",
            )
            for c in candidates
        ]

        logger.info(f"Generated {len(candidates)} thumbnail candidates for timeline {timeline_id}")

        return ThumbnailCandidatesResponse(
            timeline_id=timeline_id,
            candidates=response_candidates,
            duration=timeline.source_duration,
            message=f"Generated {len(candidates)} candidate screenshots",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Candidate generation failed for timeline {timeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{timeline_id}/thumbnail", response_model=ThumbnailResponse)
async def generate_thumbnail(
    timeline_id: str,
    request: ThumbnailGenerateRequest | None = None,
):
    """Generate a YouTube-style thumbnail for the timeline.

    Two usage modes:
    1. Auto mode (no request body): AI analyzes subtitles for best moment
    2. Manual mode (with request body):
       - timestamp: Use specific timestamp for frame extraction
       - candidate_index: Use a previously generated candidate frame

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

    # Determine timestamp or use candidate frame
    timestamp = None
    frame_path = None

    if request:
        if request.candidate_index is not None:
            # Use candidate frame
            candidates_dir = job_dir / "output" / "thumbnail_candidates"
            candidate_files = sorted(candidates_dir.glob(f"candidate_{request.candidate_index}_*.jpg"))
            if candidate_files:
                frame_path = candidate_files[0]
                logger.info(f"Using candidate frame: {frame_path}")
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Candidate {request.candidate_index} not found. Generate candidates first."
                )
        elif request.timestamp is not None:
            timestamp = request.timestamp
            logger.info(f"Using custom timestamp: {timestamp}s")

    # Generate thumbnail
    filename = f"thumbnail_{int(time.time())}.png"

    try:
        if frame_path:
            # Generate from existing frame
            thumbnail_path = await thumbnail_worker.generate_from_frame(
                title=timeline.source_title,
                subtitles=subtitles,
                frame_path=frame_path,
                output_dir=output_dir,
                filename=filename,
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
