"""Lofi Video Factory API endpoints."""

import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from loguru import logger

from app.config import settings
from app.models.lofi import (
    LofiImageInfo,
    LofiSession,
    LofiSessionCreate,
    LofiSessionStatus,
    LofiSessionUpdate,
    LofiTheme,
    LofiThemeInfo,
    MusicConfig,
    VisualConfig,
)
from app.services.lofi_manager import LofiSessionManager
from app.workers.lofi_pipeline import LofiPipelineWorker

router = APIRouter(prefix="/lofi", tags=["lofi"])

# Module-level dependencies
_session_manager: Optional[LofiSessionManager] = None
_pipeline_worker: Optional[LofiPipelineWorker] = None


def set_lofi_session_manager(manager: LofiSessionManager) -> None:
    """Set the lofi session manager instance."""
    global _session_manager
    _session_manager = manager


def set_lofi_pipeline_worker(worker: LofiPipelineWorker) -> None:
    """Set the lofi pipeline worker instance."""
    global _pipeline_worker
    _pipeline_worker = worker


def _get_manager() -> LofiSessionManager:
    if _session_manager is None:
        raise HTTPException(status_code=503, detail="Lofi session manager not initialized")
    return _session_manager


def _get_worker() -> LofiPipelineWorker:
    if _pipeline_worker is None:
        raise HTTPException(status_code=503, detail="Lofi pipeline worker not initialized")
    return _pipeline_worker


# ============ Session CRUD ============


@router.post("/sessions", response_model=LofiSession)
async def create_session(request: LofiSessionCreate):
    """Create a new lofi session."""
    manager = _get_manager()

    session = LofiSession(
        target_duration=request.target_duration,
        music_config=MusicConfig(
            source=request.music_source,
            theme=request.theme,
            model_size=request.model_size,
            segment_duration=request.segment_duration,
            crossfade_duration=request.crossfade_duration,
            ambient_sounds=request.ambient_sounds,
            ambient_volume=request.ambient_volume,
        ),
        visual_config=VisualConfig(
            mode=request.visual_mode,
            image_path=request.image_path,
        ),
        channel_id=request.channel_id,
        triggered_by=request.triggered_by,
    )
    manager.create_session(session)
    logger.info(f"Created lofi session: {session.id}")
    return session


@router.get("/sessions", response_model=List[LofiSession])
async def list_sessions(status: Optional[LofiSessionStatus] = None):
    """List lofi sessions, optionally filtered by status."""
    manager = _get_manager()
    return manager.list_sessions(status=status)


@router.get("/sessions/{session_id}", response_model=LofiSession)
async def get_session(session_id: str):
    """Get a lofi session by ID."""
    manager = _get_manager()
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/sessions/{session_id}", response_model=LofiSession)
async def update_session(session_id: str, request: LofiSessionUpdate):
    """Update a lofi session's metadata."""
    manager = _get_manager()
    session = manager.update_session(
        session_id,
        title=request.title,
        description=request.description,
        tags=request.tags,
        privacy_status=request.privacy_status,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a lofi session and its files."""
    manager = _get_manager()
    if not manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted", "session_id": session_id}


# ============ Pipeline Actions ============


@router.post("/sessions/{session_id}/generate")
async def start_generation(session_id: str, background_tasks: BackgroundTasks):
    """Start the lofi generation pipeline for a session."""
    manager = _get_manager()
    worker = _get_worker()

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in (LofiSessionStatus.PENDING, LofiSessionStatus.FAILED):
        raise HTTPException(
            status_code=400,
            detail=f"Session not in startable state: {session.status.value}",
        )

    background_tasks.add_task(worker.run_pipeline, session_id)
    logger.info(f"Started lofi pipeline for session {session_id}")
    return {"message": "Pipeline started", "session_id": session_id}


@router.post("/sessions/{session_id}/publish")
async def publish_session(session_id: str, background_tasks: BackgroundTasks):
    """Publish a reviewed session to YouTube."""
    manager = _get_manager()
    worker = _get_worker()

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != LofiSessionStatus.AWAITING_REVIEW:
        raise HTTPException(
            status_code=400,
            detail=f"Session not ready for publishing: {session.status.value}",
        )

    background_tasks.add_task(worker.publish_to_youtube, session_id)
    return {"message": "Publishing started", "session_id": session_id}


@router.post("/sessions/{session_id}/regenerate-metadata")
async def regenerate_metadata(session_id: str, background_tasks: BackgroundTasks):
    """Regenerate YouTube metadata via LLM."""
    manager = _get_manager()
    worker = _get_worker()

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    async def _regenerate():
        theme = session.music_config.theme
        duration_hours = session.target_duration / 3600
        ambient = ", ".join(session.music_config.ambient_sounds) if session.music_config.ambient_sounds else "none"
        metadata = await worker._call_llm_for_metadata(theme, duration_hours, ambient)
        manager.update_session(
            session_id,
            title=metadata.get("title"),
            description=metadata.get("description"),
            tags=metadata.get("tags"),
        )

    background_tasks.add_task(_regenerate)
    return {"message": "Metadata regeneration started", "session_id": session_id}


# ============ Media Endpoints ============


@router.get("/sessions/{session_id}/audio")
async def get_session_audio(session_id: str):
    """Stream the final audio for a session."""
    manager = _get_manager()
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.final_audio_path:
        raise HTTPException(status_code=404, detail="Audio not yet generated")
    path = Path(session.final_audio_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(path, media_type="audio/wav", filename=f"lofi_{session_id}.wav")


@router.get("/sessions/{session_id}/video")
async def get_session_video(session_id: str):
    """Stream the final video for a session."""
    manager = _get_manager()
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.final_video_path:
        raise HTTPException(status_code=404, detail="Video not yet generated")
    path = Path(session.final_video_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(path, media_type="video/mp4", filename=f"lofi_{session_id}.mp4")


@router.get("/sessions/{session_id}/thumbnail")
async def get_session_thumbnail(session_id: str):
    """Get the thumbnail image for a session."""
    manager = _get_manager()
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not yet generated")
    path = Path(session.thumbnail_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found")
    return FileResponse(path, media_type="image/png", filename=f"lofi_{session_id}_thumb.png")


# ============ Themes & Images ============


@router.get("/themes", response_model=List[LofiThemeInfo])
async def list_themes():
    """List available lofi themes with their MusicGen prompts."""
    return [
        LofiThemeInfo(
            value=theme.value,
            label=theme.label,
            musicgen_prompt=theme.musicgen_prompt,
        )
        for theme in LofiTheme
    ]


@router.get("/images", response_model=List[LofiImageInfo])
async def list_images():
    """List available background images."""
    images_dir = settings.lofi_images_dir
    if not images_dir.exists():
        return []

    images = []
    for ext in ("*.jpg", "*.jpeg", "*.png"):
        for img_path in sorted(images_dir.glob(ext)):
            images.append(
                LofiImageInfo(
                    name=img_path.stem,
                    path=str(img_path),
                )
            )
    return images


@router.post("/images/upload", response_model=LofiImageInfo)
async def upload_image(file: UploadFile = File(...)):
    """Upload a custom background image."""
    images_dir = settings.lofi_images_dir
    images_dir.mkdir(parents=True, exist_ok=True)

    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # Save file
    filename = file.filename or "custom.jpg"
    dest = images_dir / filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    logger.info(f"Uploaded lofi background image: {filename}")
    return LofiImageInfo(name=dest.stem, path=str(dest))
