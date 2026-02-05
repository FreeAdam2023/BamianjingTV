"""Creative mode API endpoints for Remotion configuration."""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.models.creative import (
    RemotionConfig,
    GenerateConfigRequest,
    GenerateConfigResponse,
    SaveConfigRequest,
    SaveConfigResponse,
    GetConfigResponse,
    create_default_config,
)
from app.services.creative_config_generator import CreativeConfigGenerator
from app.services.timeline_manager import TimelineManager
from app.workers.remotion_export import (
    creative_export_worker,
    CreativeExportStatus,
)
from app.config import settings

router = APIRouter(prefix="/creative", tags=["creative"])


# Request/Response models for render endpoints
class RenderOptions(BaseModel):
    """Options for Remotion render."""
    width: int = 1920
    height: int = 1080
    fps: int = 30
    quality: str = "high"  # high, medium, low


class RenderRequest(BaseModel):
    """Request to start a creative mode render."""
    config: Optional[RemotionConfig] = None  # If not provided, uses saved config
    options: Optional[RenderOptions] = None


class RenderResponse(BaseModel):
    """Response from render request."""
    timeline_id: str
    status: str
    message: str


class RenderStatusResponse(BaseModel):
    """Response with render status."""
    timeline_id: str
    status: str
    progress: int
    error: Optional[str] = None
    output_path: Optional[str] = None

# Module-level dependencies (set during app startup)
_timeline_manager: TimelineManager | None = None
_config_generator: CreativeConfigGenerator | None = None


def set_timeline_manager(manager: TimelineManager):
    """Set the timeline manager dependency."""
    global _timeline_manager
    _timeline_manager = manager


def set_config_generator(generator: CreativeConfigGenerator):
    """Set the config generator dependency."""
    global _config_generator
    _config_generator = generator


def _get_timeline_manager() -> TimelineManager:
    """Get the timeline manager or raise error."""
    if _timeline_manager is None:
        raise HTTPException(status_code=500, detail="Timeline manager not initialized")
    return _timeline_manager


def _get_config_generator() -> CreativeConfigGenerator:
    """Get the config generator or raise error."""
    if _config_generator is None:
        raise HTTPException(status_code=500, detail="Config generator not initialized")
    return _config_generator


@router.post("/{timeline_id}/generate-config", response_model=GenerateConfigResponse)
async def generate_config(timeline_id: str, request: GenerateConfigRequest):
    """Generate RemotionConfig from natural language description.

    Uses AI to interpret the user's description and generate appropriate
    animation settings for bilingual subtitles.
    """
    manager = _get_timeline_manager()
    generator = _get_config_generator()

    # Verify timeline exists
    timeline = manager.get(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail=f"Timeline {timeline_id} not found")

    # Generate config using AI
    config, explanation, tokens, cost = await generator.generate(
        prompt=request.prompt,
        style_preset=request.style_preset,
        previous_config=request.previous_config,
    )

    logger.info(
        f"Generated creative config for timeline {timeline_id}: "
        f"style={config.style}, tokens={tokens}, cost=${cost:.4f}"
    )

    return GenerateConfigResponse(
        config=config,
        explanation=explanation,
        tokens_used=tokens,
        cost_usd=cost,
    )


@router.post("/{timeline_id}/save-config", response_model=SaveConfigResponse)
async def save_config(timeline_id: str, request: SaveConfigRequest):
    """Save RemotionConfig to timeline.

    Persists the configuration for later use in rendering.
    """
    manager = _get_timeline_manager()

    # Verify timeline exists
    timeline = manager.get(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail=f"Timeline {timeline_id} not found")

    # Save config to timeline
    timeline.creative_config = request.config.model_dump(by_alias=True)
    manager.save(timeline)

    logger.info(f"Saved creative config for timeline {timeline_id}: style={request.config.style}")

    return SaveConfigResponse(
        timeline_id=timeline_id,
        message=f"Creative config saved (style: {request.config.style})",
    )


@router.get("/{timeline_id}/config", response_model=GetConfigResponse)
async def get_config(timeline_id: str):
    """Get stored RemotionConfig for timeline.

    Returns the previously saved configuration, or null if none exists.
    """
    manager = _get_timeline_manager()

    # Verify timeline exists
    timeline = manager.get(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail=f"Timeline {timeline_id} not found")

    if timeline.creative_config:
        try:
            config = RemotionConfig.model_validate(timeline.creative_config)
            return GetConfigResponse(
                timeline_id=timeline_id,
                config=config,
                has_config=True,
            )
        except Exception as e:
            logger.warning(f"Invalid stored config for timeline {timeline_id}: {e}")

    return GetConfigResponse(
        timeline_id=timeline_id,
        config=None,
        has_config=False,
    )


@router.delete("/{timeline_id}/config")
async def delete_config(timeline_id: str):
    """Delete stored RemotionConfig for timeline."""
    manager = _get_timeline_manager()

    # Verify timeline exists
    timeline = manager.get(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail=f"Timeline {timeline_id} not found")

    timeline.creative_config = None
    manager.save(timeline)

    logger.info(f"Deleted creative config for timeline {timeline_id}")

    return {"timeline_id": timeline_id, "message": "Creative config deleted"}


@router.get("/{timeline_id}/presets")
async def get_style_presets():
    """Get available style presets with their default configurations.

    Returns all available preset styles that users can choose from.
    """
    from app.models.creative import CreativeStyle, STYLE_PRESETS

    presets = {}
    for style in CreativeStyle:
        config = create_default_config(style)
        presets[style.value] = {
            "name": style.value.capitalize(),
            "description": _get_style_description(style),
            "config": config.model_dump(by_alias=True),
        }

    return {"presets": presets}


def _get_style_description(style) -> str:
    """Get human-readable description for a style."""
    from app.models.creative import CreativeStyle

    descriptions = {
        CreativeStyle.KARAOKE: "Words highlight one-by-one as they're spoken, like YouTube lyric videos",
        CreativeStyle.POPUP: "Subtitles bounce in with a spring effect, great for energetic content",
        CreativeStyle.SLIDE: "Subtitles slide in smoothly from the side, professional and clean",
        CreativeStyle.TYPEWRITER: "Characters appear one by one, perfect for narrative or documentary style",
        CreativeStyle.CUSTOM: "Fully customizable settings for unique effects",
    }
    return descriptions.get(style, "Custom subtitle animation style")


# ============================================================================
# Render API endpoints
# ============================================================================

@router.post("/{timeline_id}/render", response_model=RenderResponse)
async def start_render(timeline_id: str, request: RenderRequest):
    """Start a creative mode render job.

    Renders the Remotion composition with dynamic subtitles overlaid
    on the source video.

    Args:
        timeline_id: Timeline ID to render
        request: Render request with optional config override and options

    Returns:
        Render job status
    """
    manager = _get_timeline_manager()

    # Verify timeline exists
    timeline = manager.get(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail=f"Timeline {timeline_id} not found")

    # Get config from request or saved config
    config = request.config
    if config is None:
        if timeline.creative_config:
            try:
                config = RemotionConfig.model_validate(timeline.creative_config)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid saved config: {e}. Please provide a config in the request.",
                )
        else:
            # Use default config
            config = create_default_config()

    # Find source video
    job_dir = settings.jobs_dir / timeline.job_id
    source_video = job_dir / "source" / "video.mp4"
    if not source_video.exists():
        # Try alternative path
        source_video = job_dir / "video.mp4"
        if not source_video.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Source video not found for job {timeline.job_id}",
            )

    # Prepare output directory
    output_dir = job_dir / "output" / "creative"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert timeline segments to dict format
    segments = [seg.model_dump() for seg in timeline.segments]

    # Determine FPS
    fps = request.options.fps if request.options else 30

    # Submit render job
    job = await creative_export_worker.submit_job(
        timeline_id=timeline_id,
        job_id=timeline.job_id,
        segments=segments,
        config=config.model_dump(by_alias=True),
        source_video_path=source_video,
        output_dir=output_dir,
        fps=fps,
    )

    logger.info(
        f"Started creative render for timeline {timeline_id}: "
        f"style={config.style}, segments={len(segments)}"
    )

    return RenderResponse(
        timeline_id=timeline_id,
        status=job.status.value,
        message=f"Render job queued for timeline {timeline_id}",
    )


@router.get("/{timeline_id}/render/status", response_model=RenderStatusResponse)
async def get_render_status(timeline_id: str):
    """Get the status of a creative mode render job.

    Returns:
        Current render status including progress percentage
    """
    manager = _get_timeline_manager()

    # Verify timeline exists
    timeline = manager.get(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail=f"Timeline {timeline_id} not found")

    # Get job status
    status = creative_export_worker.get_job_status(timeline_id)

    return RenderStatusResponse(
        timeline_id=timeline_id,
        status=status["status"],
        progress=status["progress"],
        error=status.get("error"),
        output_path=status.get("output_path"),
    )


@router.delete("/{timeline_id}/render")
async def cancel_render(timeline_id: str):
    """Cancel a pending or running render job.

    Note: This only removes the job from the queue. If rendering
    has already started, it will continue to completion.
    """
    # For now, just return a message. Full cancellation would require
    # more complex process management.
    return {
        "timeline_id": timeline_id,
        "message": "Render cancellation requested (may not stop in-progress renders)",
    }
