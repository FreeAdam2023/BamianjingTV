"""Lofi Session Manager - CRUD operations for lofi sessions with JSON persistence."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.config import get_config
from app.models.lofi import LofiSession, LofiSessionStatus

logger = logging.getLogger(__name__)


class LofiSessionManager:
    """Manages lofi sessions with JSON file persistence."""

    def __init__(self):
        self._config = get_config()
        self._sessions: Dict[str, LofiSession] = {}
        self._storage_dir = self._config.lofi_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load_all()

    def _load_all(self) -> None:
        """Load all session metadata from disk."""
        count = 0
        for session_dir in self._storage_dir.iterdir():
            if not session_dir.is_dir():
                continue
            meta_path = session_dir / "meta.json"
            if not meta_path.exists():
                continue
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session = LofiSession(**data)
                self._sessions[session.id] = session
                count += 1
            except Exception as e:
                logger.error(f"Failed to load lofi session from {meta_path}: {e}")
        logger.info(f"Loaded {count} lofi sessions")

    def _session_dir(self, session_id: str) -> Path:
        """Get the directory for a session."""
        return self._storage_dir / session_id

    def _save_session(self, session: LofiSession) -> None:
        """Save session metadata to disk."""
        session.updated_at = datetime.now()
        session_dir = self._session_dir(session.id)
        session_dir.mkdir(parents=True, exist_ok=True)
        meta_path = session_dir / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(session.model_dump(mode="json"), f, indent=2, default=str)

    def create_session(self, session: LofiSession) -> LofiSession:
        """Create a new session entry."""
        # Ensure subdirectories exist
        session_dir = self._session_dir(session.id)
        (session_dir / "segments").mkdir(parents=True, exist_ok=True)

        self._sessions[session.id] = session
        self._save_session(session)
        logger.info(f"Created lofi session: {session.id} (theme={session.music_config.theme.value})")
        return session

    def get_session(self, session_id: str) -> Optional[LofiSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def list_sessions(self, status: Optional[LofiSessionStatus] = None) -> List[LofiSession]:
        """List sessions, optionally filtered by status, sorted by created_at descending."""
        sessions = list(self._sessions.values())
        if status is not None:
            sessions = [s for s in sessions if s.status == status]
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)

    def update_session(
        self,
        session_id: str,
        status: Optional[LofiSessionStatus] = None,
        progress: Optional[float] = None,
        error: Optional[str] = None,
        music_segments: Optional[List[str]] = None,
        final_audio_path: Optional[str] = None,
        final_video_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
        youtube_video_id: Optional[str] = None,
        youtube_url: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        privacy_status: Optional[str] = None,
        step_timings: Optional[Dict[str, float]] = None,
    ) -> Optional[LofiSession]:
        """Update a session's fields."""
        session = self._sessions.get(session_id)
        if not session:
            return None
        if status is not None:
            session.status = status
        if progress is not None:
            session.progress = progress
        if error is not None:
            session.error = error
        if music_segments is not None:
            session.music_segments = music_segments
        if final_audio_path is not None:
            session.final_audio_path = final_audio_path
        if final_video_path is not None:
            session.final_video_path = final_video_path
        if thumbnail_path is not None:
            session.thumbnail_path = thumbnail_path
        if youtube_video_id is not None:
            session.youtube_video_id = youtube_video_id
        if youtube_url is not None:
            session.youtube_url = youtube_url
        if title is not None:
            session.metadata.title = title
        if description is not None:
            session.metadata.description = description
        if tags is not None:
            session.metadata.tags = tags
        if privacy_status is not None:
            session.metadata.privacy_status = privacy_status
        if step_timings is not None:
            session.step_timings.update(step_timings)
        self._save_session(session)
        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its files."""
        if session_id not in self._sessions:
            return False
        del self._sessions[session_id]
        session_dir = self._session_dir(session_id)
        if session_dir.exists():
            shutil.rmtree(session_dir)
        logger.info(f"Deleted lofi session: {session_id}")
        return True

    def get_session_dir(self, session_id: str) -> Path:
        """Get the session directory path."""
        return self._session_dir(session_id)

    def get_stats(self) -> Dict:
        """Return statistics about sessions."""
        by_status: Dict[str, int] = {}
        for session in self._sessions.values():
            by_status[session.status.value] = by_status.get(session.status.value, 0) + 1
        return {
            "total": len(self._sessions),
            "by_status": by_status,
        }
