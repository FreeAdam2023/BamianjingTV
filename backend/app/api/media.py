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


class ChineseConversionRequest(BaseModel):
    """Request for Chinese conversion."""
    to_traditional: bool = True  # True for simplified->traditional, False for traditional->simplified


class ChineseConversionResponse(BaseModel):
    """Response for Chinese conversion."""
    timeline_id: str
    converted_count: int
    target: str  # "traditional" or "simplified"
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


class YouTubeMetadataResponse(BaseModel):
    """Response for YouTube metadata generation."""
    timeline_id: str
    title: str
    description: str
    tags: List[str]
    message: str


class UnifiedMetadataRequest(BaseModel):
    """Request for unified metadata generation."""
    instruction: str | None = None  # User instruction to guide AI
    num_title_candidates: int = 5


class UnifiedMetadataResponse(BaseModel):
    """Response for unified metadata generation (YouTube + thumbnail titles together)."""
    timeline_id: str
    youtube_title: str
    youtube_description: str
    youtube_tags: List[str]
    thumbnail_candidates: List[TitleCandidate]
    message: str


class MetadataDraft(BaseModel):
    """Draft metadata for saving/loading."""
    youtube_title: str | None = None
    youtube_description: str | None = None
    youtube_tags: List[str] | None = None
    thumbnail_candidates: List[TitleCandidate] | None = None
    instruction: str | None = None


class MetadataDraftResponse(BaseModel):
    """Response for draft metadata."""
    timeline_id: str
    draft: MetadataDraft
    has_draft: bool
    message: str


@router.post("/{timeline_id}/metadata/generate", response_model=UnifiedMetadataResponse)
async def generate_unified_metadata(
    timeline_id: str,
    request: UnifiedMetadataRequest | None = None,
):
    """Generate coordinated YouTube metadata and thumbnail titles together.

    This ensures the YouTube title and thumbnail titles are consistent.
    Both share the same user instruction for unified creative direction.

    Args:
        timeline_id: Timeline ID
        request: Optional instruction and title count

    Returns YouTube metadata (title, description, tags) and thumbnail candidates.
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
    num_candidates = request.num_title_candidates if request else 5

    try:
        result = await thumbnail_worker.generate_unified_metadata(
            title=timeline.source_title,
            subtitles=subtitles,
            source_url=timeline.source_url,
            duration=timeline.source_duration,
            num_title_candidates=num_candidates,
            user_instruction=instruction,
        )

        youtube = result.get("youtube", {})
        candidates = result.get("thumbnail_candidates", [])

        response_candidates = [
            TitleCandidate(
                index=c["index"],
                main=c["main"],
                sub=c["sub"],
                style=c.get("style", ""),
            )
            for c in candidates
        ]

        # Auto-save draft to avoid re-generation
        timeline.draft_youtube_title = youtube.get("title", "")
        timeline.draft_youtube_description = youtube.get("description", "")
        timeline.draft_youtube_tags = youtube.get("tags", [])
        timeline.draft_thumbnail_candidates = candidates
        timeline.draft_instruction = instruction
        manager.save_timeline(timeline)

        logger.info(
            f"Generated unified metadata for timeline {timeline_id}: "
            f"YouTube title={youtube.get('title', '')[:30]}..., {len(candidates)} thumbnail candidates (draft saved)"
        )

        return UnifiedMetadataResponse(
            timeline_id=timeline_id,
            youtube_title=youtube.get("title", timeline.source_title),
            youtube_description=youtube.get("description", ""),
            youtube_tags=youtube.get("tags", []),
            thumbnail_candidates=response_candidates,
            message=f"Generated YouTube metadata + {len(candidates)} thumbnail candidates (draft saved)",
        )

    except Exception as e:
        logger.exception(f"Unified metadata generation failed for timeline {timeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{timeline_id}/metadata/draft", response_model=MetadataDraftResponse)
async def get_metadata_draft(timeline_id: str):
    """Get saved metadata draft for a timeline.

    Returns any previously saved AI-generated metadata (YouTube title,
    description, tags, thumbnail candidates) to avoid re-generation.
    """
    from loguru import logger

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Check if any draft fields have content
    has_draft = any([
        timeline.draft_youtube_title,
        timeline.draft_youtube_description,
        timeline.draft_youtube_tags,
        timeline.draft_thumbnail_candidates,
    ])

    # Convert thumbnail candidates to TitleCandidate format
    candidates = None
    if timeline.draft_thumbnail_candidates:
        candidates = [
            TitleCandidate(
                index=i,
                main=c.get("main", ""),
                sub=c.get("sub", ""),
                style=c.get("style", ""),
            )
            for i, c in enumerate(timeline.draft_thumbnail_candidates)
        ]

    draft = MetadataDraft(
        youtube_title=timeline.draft_youtube_title,
        youtube_description=timeline.draft_youtube_description,
        youtube_tags=timeline.draft_youtube_tags,
        thumbnail_candidates=candidates,
        instruction=timeline.draft_instruction,
    )

    logger.info(f"Retrieved metadata draft for timeline {timeline_id}: has_draft={has_draft}")

    return MetadataDraftResponse(
        timeline_id=timeline_id,
        draft=draft,
        has_draft=has_draft,
        message="Draft retrieved" if has_draft else "No draft saved",
    )


@router.post("/{timeline_id}/metadata/draft", response_model=MetadataDraftResponse)
async def save_metadata_draft(timeline_id: str, draft: MetadataDraft):
    """Save metadata draft for a timeline.

    Saves AI-generated metadata to avoid re-generation on next visit.
    """
    from loguru import logger

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Update timeline with draft data
    if draft.youtube_title is not None:
        timeline.draft_youtube_title = draft.youtube_title
    if draft.youtube_description is not None:
        timeline.draft_youtube_description = draft.youtube_description
    if draft.youtube_tags is not None:
        timeline.draft_youtube_tags = draft.youtube_tags
    if draft.thumbnail_candidates is not None:
        timeline.draft_thumbnail_candidates = [
            {"index": c.index, "main": c.main, "sub": c.sub, "style": c.style}
            for c in draft.thumbnail_candidates
        ]
    if draft.instruction is not None:
        timeline.draft_instruction = draft.instruction

    # Save to storage
    manager.save_timeline(timeline)

    logger.info(f"Saved metadata draft for timeline {timeline_id}")

    return MetadataDraftResponse(
        timeline_id=timeline_id,
        draft=draft,
        has_draft=True,
        message="Draft saved successfully",
    )


@router.delete("/{timeline_id}/metadata/draft")
async def delete_metadata_draft(timeline_id: str):
    """Delete metadata draft for a timeline."""
    from loguru import logger

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Clear all draft fields
    timeline.draft_youtube_title = None
    timeline.draft_youtube_description = None
    timeline.draft_youtube_tags = None
    timeline.draft_thumbnail_candidates = None
    timeline.draft_instruction = None

    manager.save_timeline(timeline)

    logger.info(f"Deleted metadata draft for timeline {timeline_id}")

    return {"timeline_id": timeline_id, "message": "Draft deleted"}


@router.post("/{timeline_id}/youtube-metadata/generate", response_model=YouTubeMetadataResponse)
async def generate_youtube_metadata(timeline_id: str):
    """Generate SEO-optimized YouTube metadata (title, description, tags).

    Analyzes video content and generates:
    - Title: SEO-optimized, clickable title
    - Description: Detailed description with keywords, hashtags
    - Tags: 15-25 relevant tags for discoverability

    Returns metadata that can be used for YouTube upload.
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

    try:
        result = await thumbnail_worker.generate_youtube_metadata(
            title=timeline.source_title,
            subtitles=subtitles,
            source_url=timeline.source_url,
            duration=timeline.source_duration,
        )

        logger.info(f"Generated YouTube metadata for timeline {timeline_id}")

        return YouTubeMetadataResponse(
            timeline_id=timeline_id,
            title=result["title"],
            description=result["description"],
            tags=result["tags"],
            message="YouTube metadata generated successfully",
        )

    except Exception as e:
        logger.exception(f"YouTube metadata generation failed for timeline {timeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{timeline_id}/convert-chinese", response_model=ChineseConversionResponse)
async def convert_chinese_subtitles(
    timeline_id: str,
    request: ChineseConversionRequest,
):
    """Convert subtitle Chinese between simplified and traditional.

    Args:
        timeline_id: Timeline ID
        request: Conversion direction (to_traditional: True for S->T, False for T->S)

    If already in the target format, returns immediately without conversion.
    Subtitles are permanently stored - no need to re-convert.
    """
    from loguru import logger

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    target = "traditional" if request.to_traditional else "simplified"

    # Check if already in target format - no conversion needed
    if timeline.use_traditional_chinese == request.to_traditional:
        logger.info(
            f"Timeline {timeline_id} already in {target} Chinese, skipping conversion"
        )
        return ChineseConversionResponse(
            timeline_id=timeline_id,
            converted_count=0,
            target=target,
            message=f"Already in {target} Chinese (no conversion needed)",
        )

    try:
        import opencc
        if request.to_traditional:
            converter = opencc.OpenCC("s2t")  # Simplified to Traditional
        else:
            converter = opencc.OpenCC("t2s")  # Traditional to Simplified
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="opencc library not installed on server"
        )

    converted_count = 0
    try:
        for segment in timeline.segments:
            if segment.zh:
                original = segment.zh
                converted = converter.convert(segment.zh)
                if converted != original:
                    segment.zh = converted
                    converted_count += 1

        # Update the timeline's traditional setting
        timeline.use_traditional_chinese = request.to_traditional

        # Save the timeline (permanent storage)
        manager.save_timeline(timeline)

        logger.info(
            f"Converted {converted_count} subtitles to {target} for timeline {timeline_id}"
        )

        return ChineseConversionResponse(
            timeline_id=timeline_id,
            converted_count=converted_count,
            target=target,
            message=f"Converted {converted_count} subtitles to {target} Chinese",
        )

    except Exception as e:
        logger.exception(f"Chinese conversion failed for timeline {timeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

        # Save cover frame timestamp to timeline
        timeline.cover_frame_time = timestamp
        manager.save_timeline(timeline)

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


class RegenerateTranslationResponse(BaseModel):
    """Response for regenerate translation."""
    message: str
    updated_count: int


@router.post("/{timeline_id}/regenerate-translation")
async def regenerate_translation(timeline_id: str):
    """Regenerate translation for all segments in a timeline with SSE progress.

    Uses the existing English text (original) and re-translates to Chinese.
    This is useful if the original translation was poor or needs updating.

    Args:
        timeline_id: Timeline ID

    Returns SSE stream with progress updates, then final result.
    """
    import json
    from loguru import logger
    from fastapi.responses import StreamingResponse
    from app.workers.translation import TranslationWorker

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Determine target language based on current setting
    target_language = "zh-TW" if timeline.use_traditional_chinese else "zh-CN"

    async def generate_progress():
        """Generator that yields SSE events with progress."""
        worker = TranslationWorker()
        updated_count = 0
        total = len(timeline.segments)

        try:
            for i, segment in enumerate(timeline.segments):
                if segment.en:  # Only translate if there's English text
                    new_translation = await worker.translate_text(
                        segment.en,
                        target_language=target_language
                    )
                    if new_translation != segment.zh:
                        segment.zh = new_translation
                        updated_count += 1

                # Send progress update
                progress_data = {
                    "type": "progress",
                    "current": i + 1,
                    "total": total,
                    "updated": updated_count
                }
                yield f"data: {json.dumps(progress_data)}\n\n"

            # Save the timeline
            manager.save_timeline(timeline)

            logger.info(
                f"Regenerated translation for timeline {timeline_id}: {updated_count} segments updated"
            )

            # Send completion event
            complete_data = {
                "type": "complete",
                "message": f"Successfully regenerated translation for {updated_count} segments",
                "updated_count": updated_count
            }
            yield f"data: {json.dumps(complete_data)}\n\n"

        except Exception as e:
            logger.exception(f"Translation regeneration failed for timeline {timeline_id}: {e}")
            error_data = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
