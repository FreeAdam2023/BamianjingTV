"""Tests for MusicCommentarySessionManager."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models.music_commentary import (
    CommentaryScript,
    DifficultyLevel,
    MusicCommentarySession,
    MusicCommentaryStatus,
    MusicGenre,
    ScriptConfig,
    SongConfig,
)
from app.services.music_commentary_manager import MusicCommentarySessionManager


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def manager(temp_dir):
    with patch("app.services.music_commentary_manager.get_config") as mock_config:
        mock_config.return_value.music_commentary_dir = temp_dir
        return MusicCommentarySessionManager()


def _make_session(**kwargs) -> MusicCommentarySession:
    """Helper to create sessions with sensible defaults."""
    defaults = {
        "song_config": SongConfig(url="https://youtube.com/watch?v=test123"),
        "script_config": ScriptConfig(difficulty=DifficultyLevel.INTERMEDIATE),
    }
    defaults.update(kwargs)
    return MusicCommentarySession(**defaults)


class TestInit:
    def test_starts_empty(self, manager):
        assert manager.get_stats()["total"] == 0

    def test_loads_persisted_sessions(self, temp_dir):
        # Pre-create a session on disk
        session = _make_session()
        session_dir = temp_dir / session.id
        session_dir.mkdir()
        with open(session_dir / "meta.json", "w") as f:
            json.dump(session.model_dump(mode="json"), f, default=str)

        with patch("app.services.music_commentary_manager.get_config") as mock_config:
            mock_config.return_value.music_commentary_dir = temp_dir
            mgr = MusicCommentarySessionManager()

        assert mgr.get_stats()["total"] == 1
        loaded = mgr.get_session(session.id)
        assert loaded is not None
        assert loaded.song_config.url == session.song_config.url

    def test_handles_corrupt_file(self, temp_dir):
        corrupt_dir = temp_dir / "corrupt_session"
        corrupt_dir.mkdir()
        (corrupt_dir / "meta.json").write_text("{invalid json")

        with patch("app.services.music_commentary_manager.get_config") as mock_config:
            mock_config.return_value.music_commentary_dir = temp_dir
            mgr = MusicCommentarySessionManager()

        assert mgr.get_stats()["total"] == 0


class TestCreateSession:
    def test_creates_and_persists(self, manager, temp_dir):
        session = _make_session()
        result = manager.create_session(session)
        assert result.id == session.id

        meta_path = temp_dir / session.id / "meta.json"
        assert meta_path.exists()

        with open(meta_path) as f:
            data = json.load(f)
        assert data["song_config"]["url"] == "https://youtube.com/watch?v=test123"

    def test_creates_subdirectories(self, manager, temp_dir):
        session = _make_session()
        manager.create_session(session)
        session_dir = temp_dir / session.id
        for subdir in ("source", "transcript", "annotations", "script", "tts", "output"):
            assert (session_dir / subdir).is_dir()


class TestGetSession:
    def test_returns_session(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.get_session(session.id)
        assert result is not None
        assert result.id == session.id

    def test_returns_none_for_missing(self, manager):
        assert manager.get_session("nonexistent") is None


class TestListSessions:
    def test_returns_all(self, manager):
        for _ in range(3):
            manager.create_session(_make_session())
        assert len(manager.list_sessions()) == 3

    def test_filters_by_status(self, manager):
        s1 = _make_session()
        s2 = _make_session()
        manager.create_session(s1)
        manager.create_session(s2)
        manager.update_session(s2.id, status=MusicCommentaryStatus.FAILED)

        pending = manager.list_sessions(status=MusicCommentaryStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].id == s1.id

        failed = manager.list_sessions(status=MusicCommentaryStatus.FAILED)
        assert len(failed) == 1
        assert failed[0].id == s2.id

    def test_sorted_newest_first(self, manager):
        sessions = []
        for _ in range(3):
            s = _make_session()
            manager.create_session(s)
            sessions.append(s)
        result = manager.list_sessions()
        # Most recently updated should be first
        assert result[0].id == sessions[-1].id


class TestUpdateSession:
    def test_updates_status(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(
            session.id, status=MusicCommentaryStatus.DOWNLOADING
        )
        assert result.status == MusicCommentaryStatus.DOWNLOADING

    def test_updates_progress(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(session.id, progress=50.0)
        assert result.progress == 50.0

    def test_updates_metadata(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(
            session.id,
            title="Learn English with Rick Astley",
            description="Great song for learning",
            tags=["english", "music"],
            privacy_status="public",
        )
        assert result.metadata.title == "Learn English with Rick Astley"
        assert result.metadata.tags == ["english", "music"]
        assert result.metadata.privacy_status == "public"

    def test_updates_file_paths(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(
            session.id,
            source_audio_path="/tmp/audio.wav",
            final_video_path="/tmp/video.mp4",
            thumbnail_path="/tmp/thumb.png",
        )
        assert result.source_audio_path == "/tmp/audio.wav"
        assert result.final_video_path == "/tmp/video.mp4"
        assert result.thumbnail_path == "/tmp/thumb.png"

    def test_updates_youtube_info(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(
            session.id,
            youtube_video_id="yt_abc",
            youtube_url="https://youtube.com/watch?v=yt_abc",
        )
        assert result.youtube_video_id == "yt_abc"

    def test_updates_step_timings(self, manager):
        session = _make_session()
        manager.create_session(session)
        manager.update_session(session.id, step_timings={"download": 5.0})
        manager.update_session(session.id, step_timings={"transcribe": 10.0})
        result = manager.get_session(session.id)
        assert result.step_timings == {"download": 5.0, "transcribe": 10.0}

    def test_updates_script(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(
            session.id,
            script={"hook_text": "Welcome!", "background_text": "This song..."},
        )
        assert result.script is not None
        assert result.script.hook_text == "Welcome!"

    def test_returns_none_for_missing(self, manager):
        assert manager.update_session("nonexistent", progress=50.0) is None

    def test_persists_to_disk(self, manager, temp_dir):
        session = _make_session()
        manager.create_session(session)
        manager.update_session(session.id, progress=75.0)

        meta_path = temp_dir / session.id / "meta.json"
        with open(meta_path) as f:
            data = json.load(f)
        assert data["progress"] == 75.0


class TestDeleteSession:
    def test_deletes_session(self, manager):
        session = _make_session()
        manager.create_session(session)
        assert manager.delete_session(session.id)
        assert manager.get_session(session.id) is None

    def test_deletes_files(self, manager, temp_dir):
        session = _make_session()
        manager.create_session(session)
        session_dir = temp_dir / session.id
        assert session_dir.exists()
        manager.delete_session(session.id)
        assert not session_dir.exists()

    def test_returns_false_for_missing(self, manager):
        assert not manager.delete_session("nonexistent")


class TestGetStats:
    def test_empty(self, manager):
        stats = manager.get_stats()
        assert stats["total"] == 0
        assert stats["by_status"] == {}

    def test_counts_by_status(self, manager):
        s1 = _make_session()
        s2 = _make_session()
        s3 = _make_session()
        manager.create_session(s1)
        manager.create_session(s2)
        manager.create_session(s3)
        manager.update_session(s2.id, status=MusicCommentaryStatus.PUBLISHED)
        manager.update_session(s3.id, status=MusicCommentaryStatus.PUBLISHED)

        stats = manager.get_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["pending"] == 1
        assert stats["by_status"]["published"] == 2
