"""Music Manager - CRUD operations for music tracks with JSON persistence."""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.config import get_config
from app.models.music import MusicTrack, MusicTrackStatus

logger = logging.getLogger(__name__)


class MusicManager:
    """Manages music tracks with JSON file persistence."""

    def __init__(self):
        self._config = get_config()
        self._tracks: Dict[str, MusicTrack] = {}
        self._storage_dir = self._config.music_dir
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load_all()

    def _load_all(self) -> None:
        """Load all track metadata from disk."""
        count = 0
        for track_dir in self._storage_dir.iterdir():
            if not track_dir.is_dir():
                continue
            meta_path = track_dir / "meta.json"
            if not meta_path.exists():
                continue
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                track = MusicTrack(**data)
                self._tracks[track.id] = track
                count += 1
            except Exception as e:
                logger.error(f"Failed to load track from {meta_path}: {e}")
        logger.info(f"Loaded {count} music tracks")

    def _track_dir(self, track_id: str) -> Path:
        """Get the directory for a track."""
        return self._storage_dir / track_id

    def _save_track(self, track: MusicTrack) -> None:
        """Save track metadata to disk."""
        track_dir = self._track_dir(track.id)
        track_dir.mkdir(parents=True, exist_ok=True)
        meta_path = track_dir / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(track.model_dump(mode="json"), f, indent=2, default=str)

    def create_track(self, track: MusicTrack) -> MusicTrack:
        """Create a new track entry."""
        self._tracks[track.id] = track
        self._save_track(track)
        logger.info(f"Created music track: {track.id} - {track.title or track.prompt[:50]}")
        return track

    def get_track(self, track_id: str) -> Optional[MusicTrack]:
        """Get a track by ID."""
        return self._tracks.get(track_id)

    def list_tracks(self) -> List[MusicTrack]:
        """List all tracks sorted by created_at descending."""
        return sorted(
            self._tracks.values(),
            key=lambda t: t.created_at,
            reverse=True,
        )

    def update_track(
        self,
        track_id: str,
        status: Optional[MusicTrackStatus] = None,
        file_path: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        error: Optional[str] = None,
    ) -> Optional[MusicTrack]:
        """Update a track's metadata."""
        track = self._tracks.get(track_id)
        if not track:
            return None
        if status is not None:
            track.status = status
        if file_path is not None:
            track.file_path = file_path
        if file_size_bytes is not None:
            track.file_size_bytes = file_size_bytes
        if error is not None:
            track.error = error
        self._save_track(track)
        return track

    def delete_track(self, track_id: str) -> bool:
        """Delete a track and its files."""
        if track_id not in self._tracks:
            return False
        del self._tracks[track_id]
        track_dir = self._track_dir(track_id)
        if track_dir.exists():
            shutil.rmtree(track_dir)
        logger.info(f"Deleted music track: {track_id}")
        return True

    def get_audio_path(self, track_id: str) -> Optional[Path]:
        """Get the audio file path for a track."""
        track = self._tracks.get(track_id)
        if not track or track.status != MusicTrackStatus.READY:
            return None
        audio_path = self._track_dir(track_id) / "audio.wav"
        if audio_path.exists():
            return audio_path
        return None
