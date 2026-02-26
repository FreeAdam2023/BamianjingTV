"""Music Commentary Video Factory API endpoints."""

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from loguru import logger

from app.models.music_commentary import (
    MusicCommentarySession,
    MusicCommentarySessionCreate,
    MusicCommentarySessionUpdate,
    MusicCommentaryStatus,
    MusicGenre,
    MusicGenreInfo,
    ScriptConfig,
    SongConfig,
)
from app.services.music_commentary_manager import MusicCommentarySessionManager

router = APIRouter(prefix="/music-commentary", tags=["music-commentary"])

# Module-level dependencies
_session_manager: Optional[MusicCommentarySessionManager] = None
_pipeline_worker = None  # Optional[MusicCommentaryPipelineWorker]


def set_mc_session_manager(manager: MusicCommentarySessionManager) -> None:
    """Set the music commentary session manager instance."""
    global _session_manager
    _session_manager = manager


def set_mc_pipeline_worker(worker) -> None:
    """Set the music commentary pipeline worker instance."""
    global _pipeline_worker
    _pipeline_worker = worker


def _get_manager() -> MusicCommentarySessionManager:
    if _session_manager is None:
        raise HTTPException(
            status_code=503, detail="Music commentary session manager not initialized"
        )
    return _session_manager


def _get_worker():
    if _pipeline_worker is None:
        raise HTTPException(
            status_code=503, detail="Music commentary pipeline worker not initialized"
        )
    return _pipeline_worker


# ============ Session CRUD ============


@router.post("/sessions", response_model=MusicCommentarySession)
async def create_session(request: MusicCommentarySessionCreate):
    """Create a new music commentary session."""
    manager = _get_manager()

    session = MusicCommentarySession(
        song_config=SongConfig(
            url=request.url,
            title=request.title,
            artist=request.artist,
            genre=request.genre,
            highlight_start=request.highlight_start,
            highlight_end=request.highlight_end,
        ),
        script_config=ScriptConfig(
            difficulty=request.difficulty,
            max_lyrics_lines=request.max_lyrics_lines,
            target_duration=request.target_duration,
        ),
        triggered_by=request.triggered_by,
    )
    manager.create_session(session)
    logger.info(f"Created music commentary session: {session.id}")
    return session


@router.get("/sessions", response_model=List[MusicCommentarySession])
async def list_sessions(status: Optional[MusicCommentaryStatus] = None):
    """List music commentary sessions, optionally filtered by status."""
    manager = _get_manager()
    return manager.list_sessions(status=status)


@router.get("/sessions/{session_id}", response_model=MusicCommentarySession)
async def get_session(session_id: str):
    """Get a music commentary session by ID."""
    manager = _get_manager()
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.patch("/sessions/{session_id}", response_model=MusicCommentarySession)
async def update_session(session_id: str, request: MusicCommentarySessionUpdate):
    """Update a music commentary session's metadata."""
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
    """Delete a music commentary session and its files."""
    manager = _get_manager()
    if not manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted", "session_id": session_id}


# ============ Pipeline Actions ============


@router.post("/sessions/{session_id}/generate")
async def start_generation(session_id: str, background_tasks: BackgroundTasks):
    """Start the music commentary generation pipeline for a session."""
    manager = _get_manager()
    worker = _get_worker()

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in (
        MusicCommentaryStatus.PENDING,
        MusicCommentaryStatus.FAILED,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Session not in startable state: {session.status.value}",
        )

    background_tasks.add_task(worker.run_pipeline, session_id)
    logger.info(f"Started music commentary pipeline for session {session_id}")
    return {"message": "Pipeline started", "session_id": session_id}


@router.post("/sessions/{session_id}/publish")
async def publish_session(session_id: str, background_tasks: BackgroundTasks):
    """Publish a reviewed session to YouTube."""
    manager = _get_manager()
    worker = _get_worker()

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != MusicCommentaryStatus.AWAITING_REVIEW:
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
        metadata = await worker._generate_youtube_metadata(session)
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
    return FileResponse(
        path, media_type="audio/wav", filename=f"mc_{session_id}.wav"
    )


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
    return FileResponse(
        path, media_type="video/mp4", filename=f"mc_{session_id}.mp4"
    )


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
    return FileResponse(
        path, media_type="image/png", filename=f"mc_{session_id}_thumb.png"
    )


@router.get("/sessions/{session_id}/script")
async def get_session_script(session_id: str):
    """Get the commentary script JSON for a session."""
    manager = _get_manager()
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.script:
        raise HTTPException(status_code=404, detail="Script not yet generated")
    return session.script.model_dump()


# ============ Genres ============


@router.get("/genres", response_model=List[MusicGenreInfo])
async def list_genres():
    """List available music genres."""
    return [
        MusicGenreInfo(value=genre.value, label=genre.label)
        for genre in MusicGenre
    ]
