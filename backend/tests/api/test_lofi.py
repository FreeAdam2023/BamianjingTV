"""Tests for Lofi Video Factory API endpoints."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.lofi import (
    router,
    set_lofi_session_manager,
    set_lofi_pipeline_worker,
    set_lofi_image_pool,
)
from app.models.lofi import (
    ImageSource,
    ImageStatus,
    LofiPoolImage,
    LofiSession,
    LofiSessionStatus,
    LofiTheme,
    MusicConfig,
    VisualConfig,
)
from app.services.lofi_manager import LofiSessionManager
from app.services.lofi_image_pool import LofiImagePool
from app.workers.lofi_pipeline import LofiPipelineWorker


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def session_manager(temp_dir):
    with patch("app.services.lofi_manager.get_config") as mock_config:
        mock_config.return_value.lofi_dir = temp_dir
        return LofiSessionManager()


@pytest.fixture
def pipeline_worker():
    worker = MagicMock(spec=LofiPipelineWorker)
    worker.run_pipeline = AsyncMock()
    worker.publish_to_youtube = AsyncMock(return_value={
        "video_id": "yt123",
        "url": "https://youtube.com/watch?v=yt123",
    })
    worker._call_llm_for_metadata = AsyncMock(return_value={
        "title": "Generated Title",
        "description": "Generated Desc",
        "tags": ["lofi"],
    })
    return worker


@pytest.fixture
def image_pool(temp_dir):
    images_dir = temp_dir / "lofi_images"
    images_dir.mkdir()
    with patch("app.services.lofi_image_pool.get_config") as mock_config:
        mock_config.return_value.lofi_images_dir = images_dir
        return LofiImagePool()


@pytest.fixture
def client(session_manager, pipeline_worker, image_pool):
    app = FastAPI()
    app.include_router(router)
    set_lofi_session_manager(session_manager)
    set_lofi_pipeline_worker(pipeline_worker)
    set_lofi_image_pool(image_pool)
    return TestClient(app)


class TestCreateSession:
    def test_default(self, client):
        resp = client.post("/lofi/sessions", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["target_duration"] == 3600.0
        assert data["music_config"]["theme"] == "lofi_hip_hop"
        assert data["visual_config"]["mode"] == "static_ken_burns"
        assert len(data["id"]) == 12

    def test_custom(self, client):
        resp = client.post("/lofi/sessions", json={
            "target_duration": 7200.0,
            "theme": "jazz",
            "ambient_sounds": ["rain", "fireplace"],
            "ambient_volume": 0.5,
            "triggered_by": "n8n",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_duration"] == 7200.0
        assert data["music_config"]["theme"] == "jazz"
        assert data["music_config"]["ambient_sounds"] == ["rain", "fireplace"]
        assert data["triggered_by"] == "n8n"

    def test_invalid_theme(self, client):
        resp = client.post("/lofi/sessions", json={"theme": "nonexistent"})
        assert resp.status_code == 422

    def test_invalid_duration(self, client):
        resp = client.post("/lofi/sessions", json={"target_duration": 100.0})
        assert resp.status_code == 422


class TestListSessions:
    def test_empty(self, client):
        resp = client.get("/lofi/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_sessions(self, client):
        client.post("/lofi/sessions", json={})
        client.post("/lofi/sessions", json={"theme": "jazz"})
        resp = client.get("/lofi/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_filter_by_status(self, client, session_manager):
        client.post("/lofi/sessions", json={})
        resp = client.post("/lofi/sessions", json={"theme": "jazz"})
        session_id = resp.json()["id"]
        session_manager.update_session(session_id, status=LofiSessionStatus.AWAITING_REVIEW)

        resp = client.get("/lofi/sessions?status=pending")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "pending"

        resp = client.get("/lofi/sessions?status=awaiting_review")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "awaiting_review"


class TestGetSession:
    def test_existing(self, client):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]

        resp = client.get(f"/lofi/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == session_id

    def test_not_found(self, client):
        resp = client.get("/lofi/sessions/nonexistent")
        assert resp.status_code == 404


class TestUpdateSession:
    def test_update_metadata(self, client):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]

        resp = client.patch(f"/lofi/sessions/{session_id}", json={
            "title": "Updated Title",
            "description": "Updated Description",
            "tags": ["lofi", "chill"],
            "privacy_status": "public",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["title"] == "Updated Title"
        assert data["metadata"]["description"] == "Updated Description"
        assert data["metadata"]["tags"] == ["lofi", "chill"]
        assert data["metadata"]["privacy_status"] == "public"

    def test_partial_update(self, client):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]

        resp = client.patch(f"/lofi/sessions/{session_id}", json={
            "title": "Just Title",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata"]["title"] == "Just Title"
        assert data["metadata"]["description"] == ""

    def test_not_found(self, client):
        resp = client.patch("/lofi/sessions/nonexistent", json={"title": "X"})
        assert resp.status_code == 404


class TestDeleteSession:
    def test_delete_existing(self, client):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]

        resp = client.delete(f"/lofi/sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session_id

        resp = client.get(f"/lofi/sessions/{session_id}")
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/lofi/sessions/nonexistent")
        assert resp.status_code == 404


class TestStartGeneration:
    def test_success(self, client, pipeline_worker):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]

        resp = client.post(f"/lofi/sessions/{session_id}/generate")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Pipeline started"

    def test_not_found(self, client):
        resp = client.post("/lofi/sessions/nonexistent/generate")
        assert resp.status_code == 404

    def test_wrong_status(self, client, session_manager):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]
        session_manager.update_session(session_id, status=LofiSessionStatus.GENERATING_MUSIC)

        resp = client.post(f"/lofi/sessions/{session_id}/generate")
        assert resp.status_code == 400
        assert "not in startable state" in resp.json()["detail"]

    def test_failed_session_can_restart(self, client, session_manager):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]
        session_manager.update_session(session_id, status=LofiSessionStatus.FAILED)

        resp = client.post(f"/lofi/sessions/{session_id}/generate")
        assert resp.status_code == 200


class TestPublishSession:
    def test_success(self, client, session_manager):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]
        session_manager.update_session(session_id, status=LofiSessionStatus.AWAITING_REVIEW)

        resp = client.post(f"/lofi/sessions/{session_id}/publish")
        assert resp.status_code == 200
        assert resp.json()["message"] == "Publishing started"

    def test_not_found(self, client):
        resp = client.post("/lofi/sessions/nonexistent/publish")
        assert resp.status_code == 404

    def test_wrong_status(self, client):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]

        resp = client.post(f"/lofi/sessions/{session_id}/publish")
        assert resp.status_code == 400
        assert "not ready for publishing" in resp.json()["detail"]


class TestRegenerateMetadata:
    def test_success(self, client):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]

        resp = client.post(f"/lofi/sessions/{session_id}/regenerate-metadata")
        assert resp.status_code == 200
        assert "regeneration started" in resp.json()["message"]

    def test_not_found(self, client):
        resp = client.post("/lofi/sessions/nonexistent/regenerate-metadata")
        assert resp.status_code == 404


class TestMediaEndpoints:
    def test_audio_not_found(self, client):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]
        resp = client.get(f"/lofi/sessions/{session_id}/audio")
        assert resp.status_code == 404
        assert "not yet generated" in resp.json()["detail"]

    def test_video_not_found(self, client):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]
        resp = client.get(f"/lofi/sessions/{session_id}/video")
        assert resp.status_code == 404

    def test_thumbnail_not_found(self, client):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]
        resp = client.get(f"/lofi/sessions/{session_id}/thumbnail")
        assert resp.status_code == 404

    def test_audio_session_not_found(self, client):
        resp = client.get("/lofi/sessions/nonexistent/audio")
        assert resp.status_code == 404

    def test_audio_file_exists(self, client, session_manager, temp_dir):
        resp = client.post("/lofi/sessions", json={})
        session_id = resp.json()["id"]

        audio_path = temp_dir / "audio.wav"
        audio_path.write_bytes(b"RIFF" + b"\x00" * 100)
        session_manager.update_session(session_id, final_audio_path=str(audio_path))

        resp = client.get(f"/lofi/sessions/{session_id}/audio")
        assert resp.status_code == 200


class TestListThemes:
    def test_returns_all_themes(self, client):
        resp = client.get("/lofi/themes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 11
        values = {t["value"] for t in data}
        assert "lofi_hip_hop" in values
        assert "jazz" in values
        assert "piano" in values

    def test_theme_structure(self, client):
        resp = client.get("/lofi/themes")
        theme = resp.json()[0]
        assert "value" in theme
        assert "label" in theme
        assert "musicgen_prompt" in theme


# ============ Image Pool Endpoint Tests ============


class TestListPoolImages:
    def test_empty(self, client):
        resp = client.get("/lofi/images")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_images(self, client, image_pool):
        img = LofiPoolImage(filename="test.jpg", source=ImageSource.UPLOAD)
        image_pool.add_image(img)

        resp = client.get("/lofi/images")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == img.id
        assert data[0]["source"] == "upload"

    def test_filter_by_status(self, client, image_pool):
        img1 = LofiPoolImage(filename="a.jpg", source=ImageSource.UPLOAD, status=ImageStatus.PENDING)
        img2 = LofiPoolImage(filename="b.jpg", source=ImageSource.UPLOAD, status=ImageStatus.APPROVED)
        image_pool.add_image(img1)
        image_pool.add_image(img2)

        resp = client.get("/lofi/images?status=approved")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["status"] == "approved"

    def test_filter_by_theme(self, client, image_pool):
        img = LofiPoolImage(filename="a.jpg", source=ImageSource.UPLOAD, themes=[LofiTheme.JAZZ])
        image_pool.add_image(img)

        resp = client.get("/lofi/images?theme=jazz")
        assert len(resp.json()) == 1

        resp = client.get("/lofi/images?theme=rain")
        assert len(resp.json()) == 0


class TestGetPoolImage:
    def test_existing(self, client, image_pool):
        img = LofiPoolImage(filename="test.jpg", source=ImageSource.UPLOAD)
        image_pool.add_image(img)

        resp = client.get(f"/lofi/images/{img.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == img.id

    def test_not_found(self, client):
        resp = client.get("/lofi/images/nonexistent")
        assert resp.status_code == 404


class TestUploadPoolImage:
    def test_success(self, client, image_pool, temp_dir):
        images_dir = temp_dir / "lofi_images"
        images_dir.mkdir(exist_ok=True)

        with patch("app.api.lofi.settings") as mock_settings:
            mock_settings.lofi_images_dir = images_dir
            resp = client.post(
                "/lofi/images/upload",
                files={"file": ("test.jpg", b"fake image data", "image/jpeg")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "test.jpg"
        assert data["source"] == "upload"
        assert data["status"] == "pending"

    def test_non_image_rejected(self, client, temp_dir):
        images_dir = temp_dir / "lofi_images"
        images_dir.mkdir(exist_ok=True)

        with patch("app.api.lofi.settings") as mock_settings:
            mock_settings.lofi_images_dir = images_dir
            resp = client.post(
                "/lofi/images/upload",
                files={"file": ("test.txt", b"not an image", "text/plain")},
            )
        assert resp.status_code == 400


class TestGeneratePoolImage:
    def test_success(self, client, image_pool, temp_dir):
        images_dir = temp_dir / "lofi_images"
        images_dir.mkdir(exist_ok=True)
        fake_path = images_dir / "ai_jazz_test.png"
        fake_path.write_bytes(b"fake")

        with patch("app.workers.image_generator.generate_lofi_image", new_callable=AsyncMock, return_value=fake_path):
            resp = client.post("/lofi/images/generate", json={
                "theme": "jazz",
                "custom_prompt": "beautiful jazz bar",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "ai_generated"
        assert data["themes"] == ["jazz"]

    def test_no_model_configured(self, client):
        with patch("app.workers.image_generator.generate_lofi_image", new_callable=AsyncMock, side_effect=ValueError("image_model not configured")):
            resp = client.post("/lofi/images/generate", json={"theme": "jazz"})
        assert resp.status_code == 400


class TestSearchPixabay:
    def test_success(self, client):
        mock_results = [
            {"id": "123", "preview_url": "https://test.com/preview.jpg", "large_url": "https://test.com/large.jpg", "tags": "cozy", "width": 3840, "height": 2160},
        ]
        with patch("app.workers.pixabay_search.search_pixabay", new_callable=AsyncMock, return_value=mock_results):
            resp = client.post("/lofi/images/search-pixabay", json={"query": "cozy room"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "123"

    def test_no_api_key(self, client):
        with patch("app.workers.pixabay_search.search_pixabay", new_callable=AsyncMock, side_effect=ValueError("PIXABAY_API_KEY not configured")):
            resp = client.post("/lofi/images/search-pixabay", json={"query": "test"})
        assert resp.status_code == 400


class TestImportPixabay:
    def test_success(self, client, image_pool, temp_dir):
        images_dir = temp_dir / "lofi_images"
        images_dir.mkdir(exist_ok=True)
        fake_path = images_dir / "pixabay_123_abc.jpg"
        fake_path.write_bytes(b"fake")

        with patch("app.workers.pixabay_search.download_pixabay_image", new_callable=AsyncMock, return_value=fake_path):
            resp = client.post("/lofi/images/import-pixabay", json={
                "pixabay_id": "123",
                "url": "https://pixabay.com/large_123.jpg",
                "themes": ["jazz"],
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "pixabay"
        assert data["pixabay_id"] == "123"
        assert data["themes"] == ["jazz"]


class TestUpdateImageStatus:
    def test_approve(self, client, image_pool):
        img = LofiPoolImage(filename="test.jpg", source=ImageSource.UPLOAD)
        image_pool.add_image(img)

        resp = client.patch(f"/lofi/images/{img.id}/status", json={"status": "approved"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_reject(self, client, image_pool):
        img = LofiPoolImage(filename="test.jpg", source=ImageSource.UPLOAD)
        image_pool.add_image(img)

        resp = client.patch(f"/lofi/images/{img.id}/status", json={"status": "rejected"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_not_found(self, client):
        resp = client.patch("/lofi/images/nonexistent/status", json={"status": "approved"})
        assert resp.status_code == 404


class TestUpdateImageThemes:
    def test_update(self, client, image_pool):
        img = LofiPoolImage(filename="test.jpg", source=ImageSource.UPLOAD)
        image_pool.add_image(img)

        resp = client.patch(f"/lofi/images/{img.id}/themes", json={"themes": ["jazz", "piano"]})
        assert resp.status_code == 200
        assert resp.json()["themes"] == ["jazz", "piano"]

    def test_not_found(self, client):
        resp = client.patch("/lofi/images/nonexistent/themes", json={"themes": []})
        assert resp.status_code == 404


class TestDeletePoolImage:
    def test_success(self, client, image_pool):
        img = LofiPoolImage(filename="test.jpg", source=ImageSource.UPLOAD)
        image_pool.add_image(img)

        resp = client.delete(f"/lofi/images/{img.id}")
        assert resp.status_code == 200
        assert resp.json()["image_id"] == img.id

    def test_not_found(self, client):
        resp = client.delete("/lofi/images/nonexistent")
        assert resp.status_code == 404


class TestGetImageFile:
    def test_success(self, client, image_pool, temp_dir):
        images_dir = temp_dir / "lofi_images"
        (images_dir / "test.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        img = LofiPoolImage(filename="test.jpg", source=ImageSource.UPLOAD)
        image_pool.add_image(img)

        with patch("app.api.lofi.settings") as mock_settings:
            mock_settings.lofi_images_dir = images_dir
            resp = client.get(f"/lofi/images/{img.id}/file")
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.get("/lofi/images/nonexistent/file")
        assert resp.status_code == 404


class TestSyncImages:
    def test_sync(self, client, image_pool, temp_dir):
        images_dir = temp_dir / "lofi_images"
        (images_dir / "new1.jpg").write_bytes(b"fake")
        (images_dir / "new2.png").write_bytes(b"fake")

        resp = client.post("/lofi/images/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["added"] == 2


class TestManagerNotInitialized:
    def test_503_on_list(self):
        app = FastAPI()
        app.include_router(router)
        set_lofi_session_manager(None)
        set_lofi_pipeline_worker(None)
        set_lofi_image_pool(None)
        c = TestClient(app)
        resp = c.get("/lofi/sessions")
        assert resp.status_code == 503

    def test_503_on_create(self):
        app = FastAPI()
        app.include_router(router)
        set_lofi_session_manager(None)
        c = TestClient(app)
        resp = c.post("/lofi/sessions", json={})
        assert resp.status_code == 503

    def test_503_on_generate(self):
        app = FastAPI()
        app.include_router(router)
        set_lofi_session_manager(None)
        set_lofi_pipeline_worker(None)
        c = TestClient(app)
        resp = c.post("/lofi/sessions/test/generate")
        assert resp.status_code == 503

    def test_503_on_pool_images(self):
        app = FastAPI()
        app.include_router(router)
        set_lofi_image_pool(None)
        c = TestClient(app)
        resp = c.get("/lofi/images")
        assert resp.status_code == 503
