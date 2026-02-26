"""Tests for Music Commentary API endpoints."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.music_commentary import (
    router,
    set_mc_session_manager,
    set_mc_pipeline_worker,
)
from app.models.music_commentary import (
    CommentaryScript,
    DifficultyLevel,
    LyricsExplanation,
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
def session_manager(temp_dir):
    with patch("app.services.music_commentary_manager.get_config") as mock_config:
        mock_config.return_value.music_commentary_dir = temp_dir
        return MusicCommentarySessionManager()


@pytest.fixture
def pipeline_worker():
    worker = MagicMock()
    worker.run_pipeline = AsyncMock()
    worker.publish_to_youtube = AsyncMock(
        return_value={
            "video_id": "yt123",
            "url": "https://youtube.com/watch?v=yt123",
        }
    )
    worker._generate_youtube_metadata = AsyncMock(
        return_value={
            "title": "Learn English with Songs",
            "description": "Amazing learning content",
            "tags": ["english", "music", "learning"],
        }
    )
    return worker


@pytest.fixture
def client(session_manager, pipeline_worker):
    app = FastAPI()
    app.include_router(router)
    set_mc_session_manager(session_manager)
    set_mc_pipeline_worker(pipeline_worker)
    return TestClient(app)


def _create_session_via_api(client, **kwargs):
    """Helper to create a session via API."""
    defaults = {"url": "https://youtube.com/watch?v=test123"}
    defaults.update(kwargs)
    resp = client.post("/music-commentary/sessions", json=defaults)
    assert resp.status_code == 200
    return resp.json()


class TestCreateSession:
    def test_minimal(self, client):
        resp = client.post(
            "/music-commentary/sessions",
            json={"url": "https://youtube.com/watch?v=abc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["song_config"]["url"] == "https://youtube.com/watch?v=abc"
        assert data["status"] == "pending"
        assert data["song_config"]["genre"] == "pop"
        assert data["script_config"]["difficulty"] == "intermediate"

    def test_full(self, client):
        resp = client.post(
            "/music-commentary/sessions",
            json={
                "url": "https://youtube.com/watch?v=abc",
                "title": "Never Gonna Give You Up",
                "artist": "Rick Astley",
                "genre": "rock",
                "difficulty": "beginner",
                "max_lyrics_lines": 8,
                "target_duration": 180.0,
                "highlight_start": 30.0,
                "highlight_end": 60.0,
                "triggered_by": "n8n",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["song_config"]["title"] == "Never Gonna Give You Up"
        assert data["song_config"]["genre"] == "rock"
        assert data["script_config"]["difficulty"] == "beginner"
        assert data["script_config"]["max_lyrics_lines"] == 8
        assert data["triggered_by"] == "n8n"

    def test_missing_url(self, client):
        resp = client.post("/music-commentary/sessions", json={})
        assert resp.status_code == 422

    def test_invalid_duration(self, client):
        resp = client.post(
            "/music-commentary/sessions",
            json={"url": "https://x.com/v", "target_duration": 50.0},
        )
        assert resp.status_code == 422


class TestListSessions:
    def test_empty(self, client):
        resp = client.get("/music-commentary/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all(self, client):
        _create_session_via_api(client)
        _create_session_via_api(client, url="https://youtube.com/watch?v=other")
        resp = client.get("/music-commentary/sessions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_status(self, client, session_manager):
        data = _create_session_via_api(client)
        session_manager.update_session(
            data["id"], status=MusicCommentaryStatus.PUBLISHED
        )
        _create_session_via_api(client)

        resp = client.get("/music-commentary/sessions?status=pending")
        assert len(resp.json()) == 1

        resp = client.get("/music-commentary/sessions?status=published")
        assert len(resp.json()) == 1


class TestGetSession:
    def test_returns_session(self, client):
        data = _create_session_via_api(client)
        resp = client.get(f"/music-commentary/sessions/{data['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == data["id"]

    def test_not_found(self, client):
        resp = client.get("/music-commentary/sessions/nonexistent")
        assert resp.status_code == 404


class TestUpdateSession:
    def test_updates_metadata(self, client):
        data = _create_session_via_api(client)
        resp = client.patch(
            f"/music-commentary/sessions/{data['id']}",
            json={
                "title": "New Title",
                "description": "New desc",
                "tags": ["english"],
                "privacy_status": "public",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["metadata"]["title"] == "New Title"
        assert resp.json()["metadata"]["privacy_status"] == "public"

    def test_partial_update(self, client):
        data = _create_session_via_api(client)
        resp = client.patch(
            f"/music-commentary/sessions/{data['id']}",
            json={"title": "Only Title"},
        )
        assert resp.status_code == 200
        assert resp.json()["metadata"]["title"] == "Only Title"

    def test_not_found(self, client):
        resp = client.patch(
            "/music-commentary/sessions/nonexistent", json={"title": "X"}
        )
        assert resp.status_code == 404


class TestDeleteSession:
    def test_deletes(self, client):
        data = _create_session_via_api(client)
        resp = client.delete(f"/music-commentary/sessions/{data['id']}")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == data["id"]

        resp = client.get(f"/music-commentary/sessions/{data['id']}")
        assert resp.status_code == 404

    def test_not_found(self, client):
        resp = client.delete("/music-commentary/sessions/nonexistent")
        assert resp.status_code == 404


class TestStartGeneration:
    def test_starts_pipeline(self, client, pipeline_worker):
        data = _create_session_via_api(client)
        resp = client.post(f"/music-commentary/sessions/{data['id']}/generate")
        assert resp.status_code == 200
        assert "Pipeline started" in resp.json()["message"]

    def test_not_found(self, client):
        resp = client.post("/music-commentary/sessions/nonexistent/generate")
        assert resp.status_code == 404

    def test_wrong_status(self, client, session_manager):
        data = _create_session_via_api(client)
        session_manager.update_session(
            data["id"], status=MusicCommentaryStatus.DOWNLOADING
        )
        resp = client.post(f"/music-commentary/sessions/{data['id']}/generate")
        assert resp.status_code == 400

    def test_allows_retry_from_failed(self, client, session_manager):
        data = _create_session_via_api(client)
        session_manager.update_session(
            data["id"], status=MusicCommentaryStatus.FAILED
        )
        resp = client.post(f"/music-commentary/sessions/{data['id']}/generate")
        assert resp.status_code == 200


class TestPublishSession:
    def test_publishes(self, client, session_manager):
        data = _create_session_via_api(client)
        session_manager.update_session(
            data["id"], status=MusicCommentaryStatus.AWAITING_REVIEW
        )
        resp = client.post(f"/music-commentary/sessions/{data['id']}/publish")
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.post("/music-commentary/sessions/nonexistent/publish")
        assert resp.status_code == 404

    def test_wrong_status(self, client):
        data = _create_session_via_api(client)
        resp = client.post(f"/music-commentary/sessions/{data['id']}/publish")
        assert resp.status_code == 400


class TestRegenerateMetadata:
    def test_regenerates(self, client, session_manager):
        data = _create_session_via_api(client)
        resp = client.post(
            f"/music-commentary/sessions/{data['id']}/regenerate-metadata"
        )
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.post(
            "/music-commentary/sessions/nonexistent/regenerate-metadata"
        )
        assert resp.status_code == 404


class TestMediaEndpoints:
    def test_audio_no_file(self, client):
        data = _create_session_via_api(client)
        resp = client.get(f"/music-commentary/sessions/{data['id']}/audio")
        assert resp.status_code == 404

    def test_audio_with_file(self, client, session_manager, temp_dir):
        data = _create_session_via_api(client)
        audio_path = temp_dir / "test.wav"
        audio_path.write_bytes(b"fake wav data")
        session_manager.update_session(
            data["id"], final_audio_path=str(audio_path)
        )
        resp = client.get(f"/music-commentary/sessions/{data['id']}/audio")
        assert resp.status_code == 200

    def test_video_no_file(self, client):
        data = _create_session_via_api(client)
        resp = client.get(f"/music-commentary/sessions/{data['id']}/video")
        assert resp.status_code == 404

    def test_video_with_file(self, client, session_manager, temp_dir):
        data = _create_session_via_api(client)
        video_path = temp_dir / "test.mp4"
        video_path.write_bytes(b"fake mp4 data")
        session_manager.update_session(
            data["id"], final_video_path=str(video_path)
        )
        resp = client.get(f"/music-commentary/sessions/{data['id']}/video")
        assert resp.status_code == 200

    def test_thumbnail_no_file(self, client):
        data = _create_session_via_api(client)
        resp = client.get(f"/music-commentary/sessions/{data['id']}/thumbnail")
        assert resp.status_code == 404

    def test_thumbnail_with_file(self, client, session_manager, temp_dir):
        data = _create_session_via_api(client)
        thumb_path = temp_dir / "thumb.png"
        thumb_path.write_bytes(b"fake png data")
        session_manager.update_session(
            data["id"], thumbnail_path=str(thumb_path)
        )
        resp = client.get(f"/music-commentary/sessions/{data['id']}/thumbnail")
        assert resp.status_code == 200

    def test_audio_session_not_found(self, client):
        resp = client.get("/music-commentary/sessions/nonexistent/audio")
        assert resp.status_code == 404


class TestScript:
    def test_no_script(self, client):
        data = _create_session_via_api(client)
        resp = client.get(f"/music-commentary/sessions/{data['id']}/script")
        assert resp.status_code == 404

    def test_with_script(self, client, session_manager):
        data = _create_session_via_api(client)
        session_manager.update_session(
            data["id"],
            script={
                "hook_text": "Welcome!",
                "background_text": "Background info",
                "lyrics_explanations": [
                    {
                        "lyric_en": "Hello world",
                        "lyric_zh": "你好世界",
                        "explanation": "A greeting",
                    }
                ],
                "deep_dive_text": "Deep dive",
                "outro_text": "Bye!",
            },
        )
        resp = client.get(f"/music-commentary/sessions/{data['id']}/script")
        assert resp.status_code == 200
        script = resp.json()
        assert script["hook_text"] == "Welcome!"
        assert len(script["lyrics_explanations"]) == 1


class TestGenres:
    def test_list_genres(self, client):
        resp = client.get("/music-commentary/genres")
        assert resp.status_code == 200
        genres = resp.json()
        assert len(genres) == 10
        values = [g["value"] for g in genres]
        assert "pop" in values
        assert "hip_hop" in values
        assert "classical" in values


class TestManagerNotInitialized:
    def test_503_when_manager_not_set(self):
        app = FastAPI()
        app.include_router(router)
        set_mc_session_manager(None)
        set_mc_pipeline_worker(None)
        tc = TestClient(app)

        resp = tc.get("/music-commentary/sessions")
        assert resp.status_code == 503

    def test_503_when_worker_not_set(self, session_manager):
        app = FastAPI()
        app.include_router(router)
        set_mc_session_manager(session_manager)
        set_mc_pipeline_worker(None)
        tc = TestClient(app)

        data = _create_session_via_api(tc)
        resp = tc.post(f"/music-commentary/sessions/{data['id']}/generate")
        assert resp.status_code == 503
