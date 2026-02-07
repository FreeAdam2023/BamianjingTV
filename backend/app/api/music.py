"""Music generation API endpoints."""

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from app.models.music import (
    MusicGenerateRequest,
    MusicGenerateResponse,
    MusicTrack,
    MusicTrackStatus,
)
from app.services.music_manager import MusicManager
from app.workers.music_generator import MusicGeneratorWorker

router = APIRouter(prefix="/music", tags=["music"])

# Module-level dependencies (set via init functions)
_music_manager: Optional[MusicManager] = None
_music_generator: Optional[MusicGeneratorWorker] = None


def set_music_manager(manager: MusicManager) -> None:
    """Set the music manager instance."""
    global _music_manager
    _music_manager = manager


def set_music_generator(generator: MusicGeneratorWorker) -> None:
    """Set the music generator worker instance."""
    global _music_generator
    _music_generator = generator


def _get_manager() -> MusicManager:
    """Get the music manager, raising if not initialized."""
    if _music_manager is None:
        raise HTTPException(status_code=503, detail="Music manager not initialized")
    return _music_manager


def _get_generator() -> MusicGeneratorWorker:
    """Get the music generator, raising if not initialized."""
    if _music_generator is None:
        raise HTTPException(status_code=503, detail="Music generator not initialized")
    return _music_generator


@router.post("/generate", response_model=MusicGenerateResponse)
async def generate_music(
    request: MusicGenerateRequest,
    background_tasks: BackgroundTasks,
):
    """Start generating a music track."""
    manager = _get_manager()
    generator = _get_generator()

    if not generator.is_available:
        raise HTTPException(
            status_code=503,
            detail="Music generation unavailable (audiocraft not installed)",
        )

    # Create track with title fallback
    title = request.title or request.prompt[:60]
    track = MusicTrack(
        title=title,
        prompt=request.prompt,
        duration_seconds=request.duration_seconds,
        model_size=request.model_size,
        status=MusicTrackStatus.GENERATING,
    )
    manager.create_track(track)

    # Launch generation in background
    background_tasks.add_task(
        generator.generate_music,
        track.id,
        request.prompt,
        request.duration_seconds,
        request.model_size,
    )

    logger.info(f"Started music generation: {track.id} ({request.duration_seconds}s, {request.model_size.value})")

    return MusicGenerateResponse(track=track, message="Music generation started")


@router.get("/tracks", response_model=list[MusicTrack])
async def list_tracks():
    """List all music tracks."""
    manager = _get_manager()
    return manager.list_tracks()


@router.get("/tracks/{track_id}", response_model=MusicTrack)
async def get_track(track_id: str):
    """Get a single track by ID."""
    manager = _get_manager()
    track = manager.get_track(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track


@router.get("/tracks/{track_id}/audio")
async def get_track_audio(track_id: str):
    """Stream the audio file for a track."""
    manager = _get_manager()
    audio_path = manager.get_audio_path(track_id)
    if not audio_path:
        raise HTTPException(status_code=404, detail="Audio not available")
    return FileResponse(
        path=str(audio_path),
        media_type="audio/wav",
        filename=f"{track_id}.wav",
    )


@router.delete("/tracks/{track_id}")
async def delete_track(track_id: str):
    """Delete a track and its files."""
    manager = _get_manager()
    if not manager.delete_track(track_id):
        raise HTTPException(status_code=404, detail="Track not found")
    return {"message": "Track deleted", "track_id": track_id}


@router.get("/status")
async def get_status():
    """Get music generation status and GPU info."""
    generator = _get_generator()
    return generator.get_status()
