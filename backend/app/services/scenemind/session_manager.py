"""SceneMind session manager service for watching sessions."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from loguru import logger

from app.config import settings
from app.models.scenemind import (
    Session,
    SessionCreate,
    SessionStatus,
    SessionSummary,
    Observation,
    ObservationCreate,
    ObservationType,
)


class SceneMindSessionManager:
    """Manager for SceneMind session CRUD operations."""

    def __init__(
        self,
        sessions_dir: Optional[Path] = None,
        frames_dir: Optional[Path] = None,
    ):
        """Initialize session manager.

        Args:
            sessions_dir: Directory for session JSON files.
            frames_dir: Directory for frame captures.
        """
        self.sessions_dir = sessions_dir or settings.scenemind_sessions_dir
        self.frames_dir = frames_dir or settings.scenemind_frames_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Session] = {}
        self._observations_cache: dict[str, List[Observation]] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all sessions from disk."""
        self._cache.clear()
        self._observations_cache.clear()
        for file_path in self.sessions_dir.glob("*.json"):
            try:
                session, observations = self._load_session(file_path)
                self._cache[session.session_id] = session
                self._observations_cache[session.session_id] = observations
            except Exception as e:
                logger.warning(f"Failed to load session {file_path}: {e}")

        logger.info(f"Loaded {len(self._cache)} SceneMind sessions")

    def _load_session(self, file_path: Path) -> tuple[Session, List[Observation]]:
        """Load a session and its observations from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        observations_data = data.pop("observations", [])
        session = Session.model_validate(data)
        observations = [Observation.model_validate(obs) for obs in observations_data]

        return session, observations

    def _save_session(self, session: Session) -> None:
        """Save a session and its observations to disk."""
        file_path = self.sessions_dir / f"{session.session_id}.json"
        observations = self._observations_cache.get(session.session_id, [])

        data = session.model_dump(mode="json")
        data["observations"] = [obs.model_dump(mode="json") for obs in observations]

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_session(self, create: SessionCreate) -> Session:
        """Create a new watching session.

        Args:
            create: Session creation data

        Returns:
            Created Session object
        """
        session = Session(
            show_name=create.show_name,
            season=create.season,
            episode=create.episode,
            title=create.title,
            video_path=create.video_path,
            duration=create.duration,
        )

        self._cache[session.session_id] = session
        self._observations_cache[session.session_id] = []

        # Create frames directory for this session
        session_frames_dir = self.frames_dir / session.session_id
        session_frames_dir.mkdir(parents=True, exist_ok=True)

        self._save_session(session)
        logger.info(f"Created SceneMind session {session.session_id}: {session.display_name}")

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self._cache.get(session_id)

    def list_sessions(
        self,
        status: Optional[SessionStatus] = None,
        show_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[SessionSummary]:
        """List sessions with optional filtering.

        Args:
            status: Filter by session status
            show_name: Filter by show name
            limit: Maximum number of results

        Returns:
            List of SessionSummary objects
        """
        result = []
        for session in sorted(
            self._cache.values(),
            key=lambda s: s.updated_at,
            reverse=True,
        ):
            if status and session.status != status:
                continue
            if show_name and session.show_name != show_name:
                continue

            result.append(
                SessionSummary(
                    session_id=session.session_id,
                    show_name=session.show_name,
                    season=session.season,
                    episode=session.episode,
                    title=session.title,
                    duration=session.duration,
                    status=session.status,
                    current_time=session.current_time,
                    observation_count=session.observation_count,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                )
            )

            if len(result) >= limit:
                break

        return result

    def update_session_time(self, session_id: str, current_time: float) -> Optional[Session]:
        """Update the current playback time for a session.

        Args:
            session_id: Session ID
            current_time: Current playback time in seconds

        Returns:
            Updated Session or None if not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        session.current_time = current_time
        session.updated_at = datetime.now()
        self._save_session(session)

        return session

    def update_session_status(
        self, session_id: str, status: SessionStatus
    ) -> Optional[Session]:
        """Update the status of a session.

        Args:
            session_id: Session ID
            status: New status

        Returns:
            Updated Session or None if not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        session.status = status
        session.updated_at = datetime.now()
        self._save_session(session)
        logger.info(f"Updated session {session_id} status to {status.value}")

        return session

    def complete_session(self, session_id: str) -> Optional[Session]:
        """Mark a session as completed.

        Args:
            session_id: Session ID

        Returns:
            Updated Session or None if not found
        """
        return self.update_session_status(session_id, SessionStatus.COMPLETED)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its associated files.

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        if session_id not in self._cache:
            return False

        # Delete session file
        file_path = self.sessions_dir / f"{session_id}.json"
        if file_path.exists():
            file_path.unlink()

        # Delete frames directory
        session_frames_dir = self.frames_dir / session_id
        if session_frames_dir.exists():
            import shutil
            shutil.rmtree(session_frames_dir)

        # Remove from caches
        del self._cache[session_id]
        if session_id in self._observations_cache:
            del self._observations_cache[session_id]

        logger.info(f"Deleted SceneMind session {session_id}")
        return True

    # ============ Observation Methods ============

    def add_observation(
        self,
        session_id: str,
        create: ObservationCreate,
        frame_path: str,
        crop_path: Optional[str] = None,
    ) -> Optional[Observation]:
        """Add an observation to a session.

        Args:
            session_id: Session ID
            create: Observation creation data
            frame_path: Path to the captured frame
            crop_path: Path to the cropped region (if any)

        Returns:
            Created Observation or None if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return None

        observation = Observation(
            session_id=session_id,
            timecode=create.timecode,
            frame_path=frame_path,
            crop_path=crop_path,
            crop_region=create.crop_region,
            note=create.note,
            tag=create.tag,
        )

        if session_id not in self._observations_cache:
            self._observations_cache[session_id] = []

        self._observations_cache[session_id].append(observation)

        # Update observation count
        session.observation_count = len(self._observations_cache[session_id])
        session.updated_at = datetime.now()

        self._save_session(session)
        logger.info(
            f"Added observation {observation.id} to session {session_id} "
            f"at {observation.timecode_str}"
        )

        return observation

    def get_observations(self, session_id: str) -> List[Observation]:
        """Get all observations for a session.

        Args:
            session_id: Session ID

        Returns:
            List of Observation objects
        """
        return self._observations_cache.get(session_id, [])

    def get_observation(self, session_id: str, observation_id: str) -> Optional[Observation]:
        """Get a specific observation.

        Args:
            session_id: Session ID
            observation_id: Observation ID

        Returns:
            Observation or None if not found
        """
        observations = self.get_observations(session_id)
        for obs in observations:
            if obs.id == observation_id:
                return obs
        return None

    def delete_observation(self, session_id: str, observation_id: str) -> bool:
        """Delete an observation.

        Args:
            session_id: Session ID
            observation_id: Observation ID

        Returns:
            True if deleted, False if not found
        """
        session = self.get_session(session_id)
        if not session:
            return False

        observations = self._observations_cache.get(session_id, [])
        for i, obs in enumerate(observations):
            if obs.id == observation_id:
                # Delete frame files
                if obs.frame_path and Path(obs.frame_path).exists():
                    Path(obs.frame_path).unlink()
                if obs.crop_path and Path(obs.crop_path).exists():
                    Path(obs.crop_path).unlink()

                # Remove from list
                del observations[i]

                # Update session
                session.observation_count = len(observations)
                session.updated_at = datetime.now()
                self._save_session(session)

                logger.info(f"Deleted observation {observation_id} from session {session_id}")
                return True

        return False

    def get_stats(self) -> dict:
        """Get session statistics.

        Returns:
            Statistics dict
        """
        total = len(self._cache)
        watching = sum(1 for s in self._cache.values() if s.status == SessionStatus.WATCHING)
        completed = sum(1 for s in self._cache.values() if s.status == SessionStatus.COMPLETED)
        total_observations = sum(len(obs) for obs in self._observations_cache.values())

        return {
            "total": total,
            "watching": watching,
            "completed": completed,
            "total_observations": total_observations,
        }
