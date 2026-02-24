"""Lofi Video Factory API endpoints."""

import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel

from app.config import settings
from app.models.lofi import (
    ImageSource,
    ImageStatus,
    LofiPoolImage,
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
_image_pool = None  # Optional[LofiImagePool] — avoids circular import at module level


def set_lofi_session_manager(manager: LofiSessionManager) -> None:
    """Set the lofi session manager instance."""
    global _session_manager
    _session_manager = manager


def set_lofi_pipeline_worker(worker: LofiPipelineWorker) -> None:
    """Set the lofi pipeline worker instance."""
    global _pipeline_worker
    _pipeline_worker = worker


def set_lofi_image_pool(pool) -> None:
    """Set the lofi image pool instance."""
    global _image_pool
    _image_pool = pool


def _get_manager() -> LofiSessionManager:
    if _session_manager is None:
        raise HTTPException(status_code=503, detail="Lofi session manager not initialized")
    return _session_manager


def _get_worker() -> LofiPipelineWorker:
    if _pipeline_worker is None:
        raise HTTPException(status_code=503, detail="Lofi pipeline worker not initialized")
    return _pipeline_worker


def _get_image_pool():
    if _image_pool is None:
        raise HTTPException(status_code=503, detail="Lofi image pool not initialized")
    return _image_pool


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


# ============ Themes ============


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


# ============ Image Pool ============


@router.get("/images", response_model=List[LofiPoolImage])
async def list_images(
    status: Optional[ImageStatus] = None,
    theme: Optional[LofiTheme] = None,
    source: Optional[ImageSource] = None,
):
    """List pool images with optional filters."""
    pool = _get_image_pool()
    return pool.list_images(status=status, theme=theme, source=source)


@router.get("/images/{image_id}", response_model=LofiPoolImage)
async def get_image(image_id: str):
    """Get a single image from the pool."""
    pool = _get_image_pool()
    img = pool.get_image(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    return img


@router.post("/images/upload", response_model=LofiPoolImage)
async def upload_image(
    file: UploadFile = File(...),
    themes: Optional[str] = None,
):
    """Upload a background image and add it to the pool as PENDING."""
    pool = _get_image_pool()
    images_dir = settings.lofi_images_dir
    images_dir.mkdir(parents=True, exist_ok=True)

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    filename = file.filename or "custom.jpg"
    dest = images_dir / filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    theme_list = []
    if themes:
        for t in themes.split(","):
            t = t.strip()
            if t:
                try:
                    theme_list.append(LofiTheme(t))
                except ValueError:
                    pass

    img = LofiPoolImage(
        filename=filename,
        source=ImageSource.UPLOAD,
        status=ImageStatus.PENDING,
        themes=theme_list,
    )
    pool.add_image(img)
    logger.info(f"Uploaded lofi image: {filename} (id={img.id})")
    return img


class GenerateImageRequest(BaseModel):
    theme: LofiTheme = LofiTheme.LOFI_HIP_HOP
    custom_prompt: Optional[str] = None


@router.post("/images/generate", response_model=LofiPoolImage)
async def generate_image(request: GenerateImageRequest):
    """Generate a background image using AI and add to the pool."""
    pool = _get_image_pool()
    from app.workers.image_generator import generate_lofi_image

    try:
        path = await generate_lofi_image(
            theme=request.theme,
            custom_prompt=request.custom_prompt,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

    img = LofiPoolImage(
        filename=path.name,
        source=ImageSource.AI_GENERATED,
        status=ImageStatus.PENDING,
        themes=[request.theme],
        prompt=request.custom_prompt or None,
    )
    pool.add_image(img)
    logger.info(f"Generated AI image: {path.name} (id={img.id})")
    return img


class SearchPixabayRequest(BaseModel):
    query: str
    per_page: int = 20


@router.post("/images/search-pixabay")
async def search_pixabay_images(request: SearchPixabayRequest):
    """Search Pixabay for images. Returns preview results (not saved to pool)."""
    from app.workers.pixabay_search import search_pixabay

    try:
        results = await search_pixabay(
            query=request.query,
            per_page=request.per_page,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pixabay search failed: {e}")

    return results


class ImportPixabayRequest(BaseModel):
    pixabay_id: str
    url: str
    themes: List[LofiTheme] = []


@router.post("/images/import-pixabay", response_model=LofiPoolImage)
async def import_pixabay_image(request: ImportPixabayRequest):
    """Download and import a Pixabay image into the pool."""
    pool = _get_image_pool()
    from app.workers.pixabay_search import download_pixabay_image

    try:
        path = await download_pixabay_image(
            pixabay_id=request.pixabay_id,
            url=request.url,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pixabay download failed: {e}")

    img = LofiPoolImage(
        filename=path.name,
        source=ImageSource.PIXABAY,
        status=ImageStatus.PENDING,
        themes=request.themes,
        pixabay_id=request.pixabay_id,
        pixabay_url=request.url,
    )
    pool.add_image(img)
    logger.info(f"Imported Pixabay image: {path.name} (id={img.id})")
    return img


class UpdateStatusRequest(BaseModel):
    status: ImageStatus


@router.patch("/images/{image_id}/status", response_model=LofiPoolImage)
async def update_image_status(image_id: str, request: UpdateStatusRequest):
    """Approve or reject an image."""
    pool = _get_image_pool()
    img = pool.update_status(image_id, request.status)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    return img


class UpdateThemesRequest(BaseModel):
    themes: List[LofiTheme]


@router.patch("/images/{image_id}/themes", response_model=LofiPoolImage)
async def update_image_themes(image_id: str, request: UpdateThemesRequest):
    """Update theme tags for an image."""
    pool = _get_image_pool()
    img = pool.update_themes(image_id, request.themes)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    return img


@router.delete("/images/{image_id}")
async def delete_image(image_id: str):
    """Remove an image from the pool and delete the file."""
    pool = _get_image_pool()
    if not pool.delete_image(image_id):
        raise HTTPException(status_code=404, detail="Image not found")
    return {"message": "Image deleted", "image_id": image_id}


@router.get("/images/{image_id}/file")
async def get_image_file(image_id: str):
    """Serve an image file from the pool."""
    pool = _get_image_pool()
    img = pool.get_image(image_id)
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    path = settings.lofi_images_dir / img.filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image file not found")
    suffix = path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "image/jpeg")
    return FileResponse(path, media_type=media_type, filename=img.filename)


@router.post("/images/sync")
async def sync_images():
    """Scan disk for images not yet in the pool and add them."""
    pool = _get_image_pool()
    added = pool.sync_from_disk()
    return {"message": f"Synced {added} images from disk", "added": added}
