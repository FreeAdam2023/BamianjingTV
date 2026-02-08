"""Timeline API routes for review UI - CRUD operations."""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from fastapi.responses import FileResponse

from app.models.timeline import (
    Timeline,
    TimelineSummary,
    SubtitleStyleMode,
    SubtitleLanguageMode,
    Observation,
    ObservationCreate,
    PinnedCard,
    PinnedCardCreate,
    PinnedCardType,
)
from app.workers.frame_capture import FrameCaptureWorker
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
_frame_capture_worker: Optional[FrameCaptureWorker] = None
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


def _get_jobs_dir() -> Optional[Path]:
    """Get the jobs directory."""
    return _jobs_dir


def set_thumbnail_worker(worker: ThumbnailWorker) -> None:
    """Set the thumbnail worker instance."""
    global _thumbnail_worker
    _thumbnail_worker = worker


def set_waveform_worker(worker: WaveformWorker) -> None:
    """Set the waveform worker instance."""
    global _waveform_worker
    _waveform_worker = worker


def set_frame_capture_worker(worker: FrameCaptureWorker) -> None:
    """Set the frame capture worker instance."""
    global _frame_capture_worker
    _frame_capture_worker = worker


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


def _get_frame_capture_worker() -> FrameCaptureWorker:
    """Get the frame capture worker instance."""
    if _frame_capture_worker is None:
        raise RuntimeError("FrameCaptureWorker not initialized")
    return _frame_capture_worker


# ============ Timeline CRUD Endpoints ============


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


@router.post("/{timeline_id}/mark-reviewed")
async def mark_timeline_reviewed(timeline_id: str):
    """Mark a timeline as reviewed."""
    manager = _get_manager()
    if not manager.mark_reviewed(timeline_id):
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {"message": f"Timeline {timeline_id} marked as reviewed"}


@router.post("/{timeline_id}/subtitle-ratio")
async def set_subtitle_area_ratio(timeline_id: str, ratio: float = Query(..., ge=0.3, le=0.7)):
    """Set subtitle area ratio for WYSIWYG export layout.

    The ratio determines how much of the screen height is dedicated to subtitles.
    Valid range: 0.3 to 0.7 (30% to 70% of screen height).
    Default is 0.5 (50%).
    """
    manager = _get_manager()
    if not manager.set_subtitle_area_ratio(timeline_id, ratio):
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {
        "timeline_id": timeline_id,
        "subtitle_area_ratio": ratio,
        "message": f"Subtitle area ratio set to {ratio:.0%}",
    }


@router.get("/{timeline_id}/subtitle-style-mode")
async def get_subtitle_style_mode(timeline_id: str):
    """Get current subtitle style mode for a timeline."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {
        "timeline_id": timeline_id,
        "subtitle_style_mode": timeline.subtitle_style_mode.value,
        "modes": {
            "half_screen": "Learning mode: Video scaled to top, subtitles in bottom area",
            "floating": "Watching mode: Transparent subtitles overlaid on video",
            "none": "Dubbing mode: No subtitles",
        },
    }


@router.post("/{timeline_id}/subtitle-style-mode")
async def set_subtitle_style_mode(
    timeline_id: str,
    mode: SubtitleStyleMode = Query(..., description="Subtitle rendering mode"),
):
    """Set subtitle style mode for export.

    Modes:
    - half_screen: Learning mode - video scaled to top, subtitles in dedicated bottom area
    - floating: Watching mode - transparent subtitles overlaid on video
    - none: Dubbing mode - no subtitles rendered
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    timeline.subtitle_style_mode = mode
    manager.save_timeline(timeline)

    mode_descriptions = {
        SubtitleStyleMode.HALF_SCREEN: "Learning mode: video on top, subtitles in bottom area",
        SubtitleStyleMode.FLOATING: "Watching mode: transparent subtitles over video",
        SubtitleStyleMode.NONE: "Dubbing mode: no subtitles",
    }

    return {
        "timeline_id": timeline_id,
        "subtitle_style_mode": mode.value,
        "message": mode_descriptions.get(mode, f"Subtitle style set to {mode.value}"),
    }


@router.get("/{timeline_id}/subtitle-language-mode")
async def get_subtitle_language_mode(timeline_id: str):
    """Get current subtitle language mode for a timeline."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {
        "timeline_id": timeline_id,
        "subtitle_language_mode": timeline.subtitle_language_mode.value,
        "modes": {
            "both": "Show both English and Chinese subtitles",
            "en": "Show only English (original) subtitles",
            "zh": "Show only Chinese (translation) subtitles",
            "none": "Hide all subtitles",
        },
    }


@router.post("/{timeline_id}/subtitle-language-mode")
async def set_subtitle_language_mode(
    timeline_id: str,
    mode: SubtitleLanguageMode = Query(..., description="Subtitle language mode"),
):
    """Set which subtitle languages to display.

    Modes:
    - both: Show both English and Chinese subtitles (bilingual)
    - en: Show only English (original) subtitles
    - zh: Show only Chinese (translation) subtitles
    - none: Hide all subtitles
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    timeline.subtitle_language_mode = mode
    manager.save_timeline(timeline)

    mode_descriptions = {
        SubtitleLanguageMode.BOTH: "Bilingual: showing both EN and ZH",
        SubtitleLanguageMode.EN: "Original only: showing English",
        SubtitleLanguageMode.ZH: "Translation only: showing Chinese",
        SubtitleLanguageMode.NONE: "Hidden: no subtitles",
    }

    return {
        "timeline_id": timeline_id,
        "subtitle_language_mode": mode.value,
        "message": mode_descriptions.get(mode, f"Subtitle language set to {mode.value}"),
    }


from pydantic import BaseModel
from typing import Dict


class SpeakerNamesUpdate(BaseModel):
    """Request model for updating speaker names."""
    speaker_names: Dict[str, str]


@router.get("/{timeline_id}/speakers")
async def get_speakers(timeline_id: str):
    """Get unique speakers and their display names for a timeline."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Get unique speakers from segments
    unique_speakers = set()
    for seg in timeline.segments:
        if seg.speaker:
            unique_speakers.add(seg.speaker)

    # Build response with current names
    speakers = []
    for speaker_id in sorted(unique_speakers):
        speakers.append({
            "speaker_id": speaker_id,
            "display_name": timeline.speaker_names.get(speaker_id, speaker_id),
            "segment_count": sum(1 for seg in timeline.segments if seg.speaker == speaker_id),
        })

    return {
        "timeline_id": timeline_id,
        "speakers": speakers,
        "speaker_names": timeline.speaker_names,
    }


@router.post("/{timeline_id}/speakers")
async def update_speaker_names(timeline_id: str, update: SpeakerNamesUpdate):
    """Update speaker display names.

    Example: {"speaker_names": {"SPEAKER_0": "Elon Musk", "SPEAKER_1": "Interviewer"}}
    """
    manager = _get_manager()
    if not manager.set_speaker_names(timeline_id, update.speaker_names):
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {
        "timeline_id": timeline_id,
        "speaker_names": update.speaker_names,
        "message": f"Updated {len(update.speaker_names)} speaker name(s)",
    }


class VideoTrimUpdate(BaseModel):
    """Request model for video-level trimming."""
    trim_start: Optional[float] = None  # Set video start time (seconds)
    trim_end: Optional[float] = None  # Set video end time (seconds), None to clear


@router.get("/{timeline_id}/trim")
async def get_video_trim(timeline_id: str):
    """Get current video trim settings."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    return {
        "timeline_id": timeline_id,
        "trim_start": timeline.video_trim_start,
        "trim_end": timeline.video_trim_end,
        "source_duration": timeline.source_duration,
        "effective_duration": (timeline.video_trim_end or timeline.source_duration) - timeline.video_trim_start,
    }


@router.post("/{timeline_id}/trim")
async def set_video_trim(timeline_id: str, update: VideoTrimUpdate):
    """Set video-level trim (cut beginning/end of video).

    This is independent of subtitle segments - it trims the actual video.
    Use trim_start to cut off waiting time at the beginning.
    Use trim_end to cut off unwanted content at the end.

    Example: {"trim_start": 453.5} to start video at 7:33.5
    Example: {"trim_start": 0, "trim_end": null} to reset trim
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Validate trim values
    if update.trim_start is not None:
        if update.trim_start < 0:
            raise HTTPException(status_code=400, detail="trim_start cannot be negative")
        if update.trim_start >= timeline.source_duration:
            raise HTTPException(status_code=400, detail="trim_start cannot exceed video duration")
        timeline.video_trim_start = update.trim_start

    if update.trim_end is not None:
        if update.trim_end <= timeline.video_trim_start:
            raise HTTPException(status_code=400, detail="trim_end must be greater than trim_start")
        if update.trim_end > timeline.source_duration:
            raise HTTPException(status_code=400, detail="trim_end cannot exceed video duration")
        timeline.video_trim_end = update.trim_end
    elif "trim_end" in (update.model_dump(exclude_unset=False) or {}):
        # Explicitly set to None to clear
        timeline.video_trim_end = None

    manager.save_timeline(timeline)

    effective_duration = (timeline.video_trim_end or timeline.source_duration) - timeline.video_trim_start

    return {
        "timeline_id": timeline_id,
        "trim_start": timeline.video_trim_start,
        "trim_end": timeline.video_trim_end,
        "source_duration": timeline.source_duration,
        "effective_duration": effective_duration,
        "message": f"Video trimmed: {timeline.video_trim_start:.1f}s - {timeline.video_trim_end or timeline.source_duration:.1f}s ({effective_duration:.1f}s)",
    }


@router.delete("/{timeline_id}/trim")
async def reset_video_trim(timeline_id: str):
    """Reset video trim to show full video."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    timeline.video_trim_start = 0.0
    timeline.video_trim_end = None
    manager.save_timeline(timeline)

    return {
        "timeline_id": timeline_id,
        "trim_start": 0.0,
        "trim_end": None,
        "source_duration": timeline.source_duration,
        "message": "Video trim reset to full duration",
    }


# ============ Observation Endpoints (for WATCHING mode) ============


@router.post("/{timeline_id}/observations", response_model=Observation)
async def add_observation(timeline_id: str, create: ObservationCreate):
    """Add an observation to a timeline (captures frame automatically).

    Observations are scene captures with notes, useful in WATCHING mode.
    The frame at the specified timecode is automatically captured.
    """
    manager = _get_manager()
    worker = _get_frame_capture_worker()
    jobs_dir = _get_jobs_dir()

    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Get video path from job
    if not jobs_dir:
        raise HTTPException(status_code=500, detail="Jobs directory not configured")

    video_path = jobs_dir / timeline.job_id / "source" / "video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    # Generate observation ID for filenames
    import uuid
    observation_id = str(uuid.uuid4())[:8]

    # Capture frame(s)
    output_dir = jobs_dir / timeline.job_id / "observations"

    try:
        full_path, crop_path = await worker.capture_observation(
            video_path=str(video_path),
            timecode=create.timecode,
            output_dir=output_dir,
            observation_id=observation_id,
            crop_region=create.crop_region,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Frame capture failed: {str(e)}")

    # Create observation record
    observation = manager.add_observation(
        timeline_id=timeline_id,
        create=create,
        frame_path=str(full_path),
        crop_path=str(crop_path) if crop_path else None,
    )

    if not observation:
        raise HTTPException(status_code=500, detail="Failed to create observation")

    # Override with pre-generated ID
    observation.id = observation_id

    return observation


@router.get("/{timeline_id}/observations", response_model=List[Observation])
async def get_observations(timeline_id: str):
    """Get all observations for a timeline."""
    manager = _get_manager()

    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    return manager.get_observations(timeline_id)


@router.get("/{timeline_id}/observations/{observation_id}", response_model=Observation)
async def get_observation(timeline_id: str, observation_id: str):
    """Get a specific observation."""
    manager = _get_manager()

    observation = manager.get_observation(timeline_id, observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")

    return observation


@router.delete("/{timeline_id}/observations/{observation_id}")
async def delete_observation(timeline_id: str, observation_id: str):
    """Delete an observation."""
    manager = _get_manager()

    if not manager.delete_observation(timeline_id, observation_id):
        raise HTTPException(status_code=404, detail="Observation not found")

    return {"message": "Observation deleted", "observation_id": observation_id}


@router.get("/{timeline_id}/observations/{observation_id}/frame")
async def get_observation_frame(
    timeline_id: str,
    observation_id: str,
    crop: bool = Query(default=False, description="Return cropped frame if available"),
):
    """Get the captured frame image for an observation."""
    manager = _get_manager()

    observation = manager.get_observation(timeline_id, observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")

    # Determine which frame to return
    if crop and observation.crop_path:
        frame_path = Path(observation.crop_path)
    else:
        frame_path = Path(observation.frame_path)

    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Frame file not found")

    return FileResponse(
        frame_path,
        media_type="image/png",
        filename=frame_path.name,
    )


# ============ AI Chat ============

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Request model for AI chat."""
    message: str
    include_transcript: bool = True
    current_time: Optional[float] = None  # Current playback position in seconds
    image: Optional[str] = None  # Base64 encoded image (data:image/jpeg;base64,...)


class ChatResponse(BaseModel):
    """Response model for AI chat."""
    response: str
    tokens_used: int = 0


@router.post("/{timeline_id}/chat", response_model=ChatResponse)
async def chat_with_ai(timeline_id: str, request: ChatRequest):
    """
    Chat with AI about the video content.

    The AI has access to the full transcript and can answer questions about:
    - Video content and topics
    - Key points and highlights
    - Recommendations for what to keep/drop
    - Translations and language questions
    """
    from app.config import settings
    from loguru import logger
    import asyncio

    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Find current segment based on playback position
    current_segment = None
    current_segment_context = ""
    if request.current_time is not None and timeline.segments:
        for seg in timeline.segments:
            if seg.start <= request.current_time <= seg.end:
                current_segment = seg
                break
        # If not exactly in a segment, find the closest one
        if not current_segment and timeline.segments:
            closest = min(timeline.segments, key=lambda s: abs(s.start - request.current_time))
            if abs(closest.start - request.current_time) < 5:  # Within 5 seconds
                current_segment = closest

        if current_segment:
            current_segment_context = f"""
【当前播放位置】 {request.current_time:.1f}秒
【当前台词】
  英文: {current_segment.en or "(无)"}
  中文: {current_segment.zh or "(无)"}
  时间: {current_segment.start:.1f}s - {current_segment.end:.1f}s

当用户说"这个台词"、"这句话"、"当前内容"时，指的是上面这句台词。
"""

    # Build transcript context
    transcript_context = ""
    if request.include_transcript and timeline.segments:
        lines = []
        for seg in timeline.segments:
            time_str = f"[{seg.start:.1f}s]"
            text = seg.en or ""
            translation = seg.zh or ""
            # Mark current segment
            marker = " ◀ 当前" if current_segment and seg.id == current_segment.id else ""
            if translation:
                lines.append(f"{time_str} {text} | {translation}{marker}")
            else:
                lines.append(f"{time_str} {text}{marker}")
        transcript_context = "\n".join(lines)

    # Build system prompt
    system_prompt = f"""你是一个视频内容分析助手。你可以帮助用户理解和分析视频内容。

视频标题: {timeline.source_title or "未知"}
视频时长: {timeline.source_duration:.0f}秒
片段数量: {len(timeline.segments)}
{current_segment_context}
{"完整字幕内容：" if transcript_context else "（无字幕）"}
{transcript_context}

你可以：
1. 回答关于视频内容的问题
2. 总结视频的主要观点
3. 找出有趣或重要的片段
4. 帮助用户决定哪些片段值得保留
5. 解释翻译或语言相关的问题
6. 分析用户截取的视频画面（如果提供）

请用简洁的中文回答。如果引用具体片段，请标注时间戳。
如果用户发送了视频截图，请结合当前台词和画面内容来回答问题。"""

    # Call LLM
    try:
        if settings.is_azure:
            from openai import AsyncAzureOpenAI
            azure_endpoint = settings.llm_base_url.split("/openai/")[0]
            client = AsyncAzureOpenAI(
                api_key=settings.llm_api_key,
                api_version=settings.azure_api_version,
                azure_endpoint=azure_endpoint,
            )
            model = settings.azure_deployment_name
        else:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )
            model = settings.llm_model

        # Build user message content (with optional image)
        if request.image:
            # GPT-4o vision format: content is a list
            user_content = [
                {"type": "text", "text": request.message},
                {
                    "type": "image_url",
                    "image_url": {"url": request.image, "detail": "low"},
                },
            ]
        else:
            user_content = request.message

        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.7,
                max_tokens=1000,
            ),
            timeout=60,
        )

        content = response.choices[0].message.content or "抱歉，我无法生成回答。"
        tokens = response.usage.total_tokens if response.usage else 0

        return ChatResponse(response=content.strip(), tokens_used=tokens)

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="AI响应超时，请重试")
    except Exception as e:
        logger.error(f"AI chat failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI服务错误: {str(e)}")


# ============ Pinned Cards Endpoints ============


@router.get("/{timeline_id}/pinned-cards", response_model=List[PinnedCard])
async def get_pinned_cards(timeline_id: str):
    """Get all pinned cards for a timeline."""
    manager = _get_manager()

    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    return manager.get_pinned_cards(timeline_id)


@router.post("/{timeline_id}/pinned-cards", response_model=PinnedCard)
async def pin_card(timeline_id: str, create: PinnedCardCreate):
    """Pin a card to a timeline.

    The card will be displayed in the right side panel during video export.
    Display timing is automatically calculated to avoid overlaps.
    """
    manager = _get_manager()

    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    try:
        pinned = manager.add_pinned_card(timeline_id, create)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if not pinned:
        raise HTTPException(status_code=500, detail="Failed to pin card")

    return pinned


@router.delete("/{timeline_id}/pinned-cards/{card_id}")
async def unpin_card(timeline_id: str, card_id: str):
    """Remove a pinned card from a timeline."""
    manager = _get_manager()

    if not manager.remove_pinned_card(timeline_id, card_id):
        raise HTTPException(status_code=404, detail="Pinned card not found")

    return {"message": "Card unpinned", "card_id": card_id}


@router.get("/{timeline_id}/pinned-cards/check/{card_type}/{card_id}")
async def check_card_pinned(
    timeline_id: str,
    card_type: str,
    card_id: str,
    segment_id: Optional[int] = None,
):
    """Check if a specific card is pinned to the timeline.

    Args:
        timeline_id: Timeline ID
        card_type: Card type (word or entity)
        card_id: The card identifier (word string or entity QID)
        segment_id: Optional segment ID for per-segment check

    Returns:
        Object with is_pinned boolean and optional pin_id
    """
    manager = _get_manager()

    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    return manager.is_card_pinned(timeline_id, card_type, card_id, segment_id)


class CardDisplayDurationUpdate(BaseModel):
    """Request model for updating card display duration."""
    duration: float = Query(..., ge=3.0, le=15.0, description="Display duration in seconds")


@router.post("/{timeline_id}/pinned-cards/duration")
async def set_card_display_duration(
    timeline_id: str,
    duration: float = Query(..., ge=3.0, le=15.0, description="Display duration in seconds"),
):
    """Set the default display duration for pinned cards.

    Duration range: 3-15 seconds (default: 7 seconds).
    Recommended: 5-10 seconds for optimal reading time.
    """
    manager = _get_manager()

    if not manager.set_card_display_duration(timeline_id, duration):
        raise HTTPException(status_code=404, detail="Timeline not found")

    return {
        "timeline_id": timeline_id,
        "card_display_duration": duration,
        "message": f"Card display duration set to {duration}s",
    }


@router.get("/{timeline_id}/pinned-cards/description")
async def get_pinned_cards_description(
    timeline_id: str,
    include_timestamps: bool = Query(default=True, description="Include video timestamps"),
):
    """Get YouTube description text with word and entity lists.

    This generates a formatted description that can be added to YouTube video
    description, including:
    - Word list with IPA pronunciation and Chinese definitions
    - Entity list with Wikipedia links

    Use this to help viewers learn vocabulary from your video.
    """
    manager = _get_manager()

    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    description = timeline.generate_pinned_cards_description(
        include_timestamps=include_timestamps
    )

    return {
        "timeline_id": timeline_id,
        "description": description,
        "word_count": len([c for c in timeline.pinned_cards if c.card_type.value == "word"]),
        "entity_count": len([c for c in timeline.pinned_cards if c.card_type.value == "entity"]),
        "message": "Description generated successfully" if description else "No pinned cards to describe",
    }
