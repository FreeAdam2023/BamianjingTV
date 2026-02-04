"""SceneMind API endpoints for watching sessions and observations."""

import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from loguru import logger

from app.config import settings
from app.models.scenemind import (
    Session,
    SessionCreate,
    SessionStatus,
    SessionSummary,
    Observation,
    ObservationCreate,
)
from app.services.scenemind import SceneMindSessionManager
from app.workers.scenemind import FrameCaptureWorker


router = APIRouter(prefix="/scenemind", tags=["scenemind"])

# Module-level references (set during startup)
_session_manager: Optional[SceneMindSessionManager] = None
_frame_capture_worker: Optional[FrameCaptureWorker] = None


def set_session_manager(manager: SceneMindSessionManager) -> None:
    """Set the session manager instance."""
    global _session_manager
    _session_manager = manager


def set_frame_capture_worker(worker: FrameCaptureWorker) -> None:
    """Set the frame capture worker instance."""
    global _frame_capture_worker
    _frame_capture_worker = worker


def _get_session_manager() -> SceneMindSessionManager:
    """Get the session manager, raising if not initialized."""
    if _session_manager is None:
        raise HTTPException(status_code=500, detail="Session manager not initialized")
    return _session_manager


def _get_frame_capture_worker() -> FrameCaptureWorker:
    """Get the frame capture worker, raising if not initialized."""
    if _frame_capture_worker is None:
        raise HTTPException(status_code=500, detail="Frame capture worker not initialized")
    return _frame_capture_worker


# ============ Upload Endpoint ============


@router.post("/upload")
async def upload_video(file: UploadFile = File(...)) -> dict:
    """Upload a video file for a new session.

    Returns the server path to use when creating a session.
    """
    # Validate file type
    allowed_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
    file_ext = Path(file.filename or "video.mp4").suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Check file size (from content-length header if available)
    max_size = settings.max_upload_size_mb * 1024 * 1024

    # Generate unique filename
    video_id = str(uuid.uuid4())[:8]
    safe_filename = f"{video_id}{file_ext}"
    video_path = settings.scenemind_videos_dir / safe_filename

    # Stream file to disk
    try:
        total_size = 0
        with open(video_path, "wb") as buffer:
            while chunk := await file.read(8 * 1024 * 1024):  # 8MB chunks
                total_size += len(chunk)
                if total_size > max_size:
                    buffer.close()
                    video_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB"
                    )
                buffer.write(chunk)

        logger.info(f"Uploaded video: {video_path} ({total_size / 1024 / 1024:.1f}MB)")

        return {
            "video_path": str(video_path),
            "filename": safe_filename,
            "size_mb": round(total_size / 1024 / 1024, 2),
        }
    except HTTPException:
        raise
    except Exception as e:
        video_path.unlink(missing_ok=True)
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/sessions/with-upload", response_model=Session)
async def create_session_with_upload(
    file: UploadFile = File(...),
    show_name: str = Form(...),
    season: int = Form(...),
    episode: int = Form(...),
    title: str = Form(""),
) -> Session:
    """Create a session with video upload in one request."""
    manager = _get_session_manager()
    worker = _get_frame_capture_worker()

    # Upload the video first
    upload_result = await upload_video(file)
    video_path = upload_result["video_path"]

    # Get video duration
    duration = 0
    try:
        duration = await worker.get_video_duration(video_path)
    except Exception as e:
        logger.warning(f"Could not get video duration: {e}")

    # Create the session
    create = SessionCreate(
        show_name=show_name,
        season=season,
        episode=episode,
        title=title,
        video_path=video_path,
        duration=duration,
    )

    session = manager.create_session(create)
    return session


# ============ Session Endpoints ============


@router.post("/sessions", response_model=Session)
async def create_session(create: SessionCreate) -> Session:
    """Create a new watching session."""
    manager = _get_session_manager()
    worker = _get_frame_capture_worker()

    # Validate video path exists
    video_path = Path(create.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail=f"Video file not found: {create.video_path}")

    # Get video duration if not provided
    if create.duration <= 0:
        try:
            duration = await worker.get_video_duration(create.video_path)
            create = SessionCreate(
                show_name=create.show_name,
                season=create.season,
                episode=create.episode,
                title=create.title,
                video_path=create.video_path,
                duration=duration,
            )
        except Exception as e:
            logger.warning(f"Could not get video duration: {e}")

    session = manager.create_session(create)
    return session


@router.get("/sessions", response_model=List[SessionSummary])
async def list_sessions(
    status: Optional[SessionStatus] = None,
    show_name: Optional[str] = None,
    limit: int = Query(default=100, le=500),
) -> List[SessionSummary]:
    """List watching sessions with optional filtering."""
    manager = _get_session_manager()
    return manager.list_sessions(status=status, show_name=show_name, limit=limit)


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(session_id: str) -> Session:
    """Get a specific session."""
    manager = _get_session_manager()
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> dict:
    """Delete a session and its files."""
    manager = _get_session_manager()
    if not manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted", "session_id": session_id}


@router.post("/sessions/{session_id}/complete")
async def complete_session(session_id: str) -> Session:
    """Mark a session as completed."""
    manager = _get_session_manager()
    session = manager.complete_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/time")
async def update_session_time(session_id: str, current_time: float) -> Session:
    """Update the current playback time."""
    manager = _get_session_manager()
    session = manager.update_session_time(session_id, current_time)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ============ Observation Endpoints ============


@router.post("/sessions/{session_id}/observations", response_model=Observation)
async def add_observation(session_id: str, create: ObservationCreate) -> Observation:
    """Add an observation to a session (captures frame automatically)."""
    manager = _get_session_manager()
    worker = _get_frame_capture_worker()

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Generate observation ID first to use in filenames
    import uuid
    observation_id = str(uuid.uuid4())[:8]

    # Capture frame(s)
    output_dir = settings.scenemind_frames_dir / session_id

    try:
        full_path, crop_path = await worker.capture_observation(
            video_path=session.video_path,
            timecode=create.timecode,
            output_dir=output_dir,
            observation_id=observation_id,
            crop_region=create.crop_region,
        )
    except Exception as e:
        logger.error(f"Frame capture failed: {e}")
        raise HTTPException(status_code=500, detail=f"Frame capture failed: {str(e)}")

    # Create observation record
    observation = manager.add_observation(
        session_id=session_id,
        create=create,
        frame_path=str(full_path),
        crop_path=str(crop_path) if crop_path else None,
    )

    if not observation:
        raise HTTPException(status_code=500, detail="Failed to create observation")

    # Override with pre-generated ID
    observation.id = observation_id

    return observation


@router.get("/sessions/{session_id}/observations", response_model=List[Observation])
async def get_observations(session_id: str) -> List[Observation]:
    """Get all observations for a session."""
    manager = _get_session_manager()

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return manager.get_observations(session_id)


@router.get("/sessions/{session_id}/observations/{observation_id}", response_model=Observation)
async def get_observation(session_id: str, observation_id: str) -> Observation:
    """Get a specific observation."""
    manager = _get_session_manager()

    observation = manager.get_observation(session_id, observation_id)
    if not observation:
        raise HTTPException(status_code=404, detail="Observation not found")

    return observation


@router.delete("/sessions/{session_id}/observations/{observation_id}")
async def delete_observation(session_id: str, observation_id: str) -> dict:
    """Delete an observation."""
    manager = _get_session_manager()

    if not manager.delete_observation(session_id, observation_id):
        raise HTTPException(status_code=404, detail="Observation not found")

    return {"message": "Observation deleted", "observation_id": observation_id}


# ============ Media Endpoints ============


@router.get("/sessions/{session_id}/video")
async def stream_video(session_id: str):
    """Stream the video file for a session."""
    manager = _get_session_manager()

    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    video_path = Path(session.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=video_path.name,
    )


@router.get("/sessions/{session_id}/frames/{filename}")
async def get_frame(session_id: str, filename: str):
    """Get a captured frame image."""
    frame_path = settings.scenemind_frames_dir / session_id / filename

    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Frame not found")

    return FileResponse(
        frame_path,
        media_type="image/png",
        filename=filename,
    )


# ============ Stats Endpoint ============


@router.get("/stats")
async def get_stats() -> dict:
    """Get SceneMind statistics."""
    manager = _get_session_manager()
    return manager.get_stats()


# ============ Video Info Endpoint ============


@router.post("/video-info")
async def get_video_info(video_path: str) -> dict:
    """Get video information (duration, dimensions)."""
    worker = _get_frame_capture_worker()

    path = Path(video_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail="Video file not found")

    try:
        info = await worker.get_video_info(video_path)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get video info: {str(e)}")
