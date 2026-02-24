"""Tests for LofiSessionManager service."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models.lofi import (
    LofiSession,
    LofiSessionStatus,
    LofiTheme,
    MusicConfig,
    VisualConfig,
)
from app.services.lofi_manager import LofiSessionManager


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def manager(temp_dir):
    with patch("app.services.lofi_manager.get_config") as mock_config:
        mock_config.return_value.lofi_dir = temp_dir
        return LofiSessionManager()


def _make_session(**kwargs) -> LofiSession:
    """Helper to create a session with sensible defaults."""
    defaults = {
        "target_duration": 3600.0,
        "music_config": MusicConfig(theme=LofiTheme.LOFI_HIP_HOP),
    }
    defaults.update(kwargs)
    return LofiSession(**defaults)


class TestInit:
    def test_empty_directory(self, manager):
        assert manager.get_stats()["total"] == 0

    def test_loads_persisted_sessions(self, temp_dir):
        # Pre-create a session on disk
        session = _make_session()
        session_dir = temp_dir / session.id
        session_dir.mkdir(parents=True)
        meta_path = session_dir / "meta.json"
        meta_path.write_text(
            json.dumps(session.model_dump(mode="json"), default=str),
            encoding="utf-8",
        )

        with patch("app.services.lofi_manager.get_config") as mock_config:
            mock_config.return_value.lofi_dir = temp_dir
            mgr = LofiSessionManager()
        assert mgr.get_stats()["total"] == 1
        assert mgr.get_session(session.id) is not None

    def test_corrupt_meta_file_skipped(self, temp_dir):
        bad_dir = temp_dir / "bad_session"
        bad_dir.mkdir()
        (bad_dir / "meta.json").write_text("{invalid json!!!", encoding="utf-8")

        with patch("app.services.lofi_manager.get_config") as mock_config:
            mock_config.return_value.lofi_dir = temp_dir
            mgr = LofiSessionManager()
        assert mgr.get_stats()["total"] == 0


class TestCreateSession:
    def test_creates_and_persists(self, manager, temp_dir):
        session = _make_session()
        result = manager.create_session(session)
        assert result.id == session.id
        assert manager.get_stats()["total"] == 1

        # Check file on disk
        meta_path = temp_dir / session.id / "meta.json"
        assert meta_path.exists()
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        assert data["id"] == session.id

    def test_creates_segments_dir(self, manager, temp_dir):
        session = _make_session()
        manager.create_session(session)
        assert (temp_dir / session.id / "segments").is_dir()


class TestGetSession:
    def test_existing(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.get_session(session.id)
        assert result is not None
        assert result.id == session.id

    def test_not_found(self, manager):
        assert manager.get_session("nonexistent") is None


class TestListSessions:
    def test_empty(self, manager):
        assert manager.list_sessions() == []

    def test_sorted_by_created_at(self, manager):
        import time
        s1 = _make_session()
        manager.create_session(s1)
        time.sleep(0.01)
        s2 = _make_session()
        manager.create_session(s2)
        result = manager.list_sessions()
        assert len(result) == 2
        assert result[0].id == s2.id  # newest first

    def test_filter_by_status(self, manager):
        s1 = _make_session()
        manager.create_session(s1)
        s2 = _make_session()
        s2.status = LofiSessionStatus.AWAITING_REVIEW
        manager.create_session(s2)

        pending = manager.list_sessions(status=LofiSessionStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].id == s1.id

        review = manager.list_sessions(status=LofiSessionStatus.AWAITING_REVIEW)
        assert len(review) == 1
        assert review[0].id == s2.id


class TestUpdateSession:
    def test_update_status(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(session.id, status=LofiSessionStatus.GENERATING_MUSIC)
        assert result.status == LofiSessionStatus.GENERATING_MUSIC

    def test_update_progress(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(session.id, progress=50.0)
        assert result.progress == 50.0

    def test_update_error(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(session.id, error="something failed")
        assert result.error == "something failed"

    def test_update_music_segments(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(
            session.id,
            music_segments=["/path/seg1.wav", "/path/seg2.wav"],
        )
        assert result.music_segments == ["/path/seg1.wav", "/path/seg2.wav"]

    def test_update_final_paths(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(
            session.id,
            final_audio_path="/path/audio.wav",
            final_video_path="/path/video.mp4",
            thumbnail_path="/path/thumb.png",
        )
        assert result.final_audio_path == "/path/audio.wav"
        assert result.final_video_path == "/path/video.mp4"
        assert result.thumbnail_path == "/path/thumb.png"

    def test_update_youtube_info(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(
            session.id,
            youtube_video_id="abc123",
            youtube_url="https://youtube.com/watch?v=abc123",
        )
        assert result.youtube_video_id == "abc123"
        assert result.youtube_url == "https://youtube.com/watch?v=abc123"

    def test_update_metadata(self, manager):
        session = _make_session()
        manager.create_session(session)
        result = manager.update_session(
            session.id,
            title="New Title",
            description="New Desc",
            tags=["a", "b"],
            privacy_status="public",
        )
        assert result.metadata.title == "New Title"
        assert result.metadata.description == "New Desc"
        assert result.metadata.tags == ["a", "b"]
        assert result.metadata.privacy_status == "public"

    def test_update_step_timings(self, manager):
        session = _make_session()
        manager.create_session(session)
        manager.update_session(session.id, step_timings={"music_generation": 120.5})
        result = manager.update_session(session.id, step_timings={"concatenation": 15.0})
        assert result.step_timings == {"music_generation": 120.5, "concatenation": 15.0}

    def test_update_not_found(self, manager):
        result = manager.update_session("nonexistent", status=LofiSessionStatus.FAILED)
        assert result is None

    def test_update_persists(self, manager, temp_dir):
        session = _make_session()
        manager.create_session(session)
        manager.update_session(session.id, title="Updated Title")

        meta_path = temp_dir / session.id / "meta.json"
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        assert data["metadata"]["title"] == "Updated Title"

    def test_updated_at_changes(self, manager):
        import time
        session = _make_session()
        manager.create_session(session)
        original_updated = session.updated_at
        time.sleep(0.01)
        result = manager.update_session(session.id, progress=10.0)
        assert result.updated_at > original_updated


class TestDeleteSession:
    def test_delete_existing(self, manager, temp_dir):
        session = _make_session()
        manager.create_session(session)
        assert manager.get_stats()["total"] == 1

        result = manager.delete_session(session.id)
        assert result is True
        assert manager.get_stats()["total"] == 0
        assert manager.get_session(session.id) is None
        assert not (temp_dir / session.id).exists()

    def test_delete_not_found(self, manager):
        assert manager.delete_session("nonexistent") is False


class TestGetSessionDir:
    def test_returns_correct_path(self, manager, temp_dir):
        path = manager.get_session_dir("test123")
        assert path == temp_dir / "test123"


class TestGetStats:
    def test_empty(self, manager):
        stats = manager.get_stats()
        assert stats["total"] == 0
        assert stats["by_status"] == {}

    def test_with_sessions(self, manager):
        s1 = _make_session()
        manager.create_session(s1)
        s2 = _make_session()
        s2.status = LofiSessionStatus.AWAITING_REVIEW
        manager.create_session(s2)
        s3 = _make_session()
        manager.create_session(s3)

        stats = manager.get_stats()
        assert stats["total"] == 3
        assert stats["by_status"]["pending"] == 2
        assert stats["by_status"]["awaiting_review"] == 1
