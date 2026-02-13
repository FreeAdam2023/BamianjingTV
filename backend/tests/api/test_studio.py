"""Tests for Virtual Studio API endpoints."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.studio import router, set_studio_manager
from app.models.studio import ScenePreset, WeatherType
from app.services.studio_manager import StudioManager


@pytest.fixture
def temp_state_file():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "studio_state.json"


@pytest.fixture
def studio_manager(temp_state_file):
    return StudioManager(
        ue_base_url="http://fake-ue:30010",
        pixel_streaming_url="http://fake-ue:80",
        state_file=temp_state_file,
    )


@pytest.fixture
def client(studio_manager):
    app = FastAPI()
    app.include_router(router)
    set_studio_manager(studio_manager)
    return TestClient(app)


class TestGetStatus:
    def test_returns_state(self, client):
        resp = client.get("/studio/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["scene"] == "modern_office"
        assert data["ue_connected"] is False
        assert data["pixel_streaming_url"] == "http://fake-ue:80"


class TestGetPresets:
    def test_returns_all_presets(self, client):
        resp = client.get("/studio/presets")
        assert resp.status_code == 200
        data = resp.json()
        assert "modern_office" in data["scenes"]
        assert "clear" in data["weather_types"]
        assert "idle" in data["character_actions"]
        assert "neutral" in data["character_expressions"]
        assert "interview" in data["lighting_presets"]


class TestSetScene:
    def test_success(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            resp = client.post("/studio/scene", json={"preset": "news_desk"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "news_desk" in data["message"]
        assert data["state"]["scene"] == "news_desk"

    def test_ue_offline(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            resp = client.post("/studio/scene", json={"preset": "news_desk"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "unreachable" in data["message"]
        assert data["state"]["scene"] == "modern_office"  # unchanged

    def test_invalid_preset(self, client):
        resp = client.post("/studio/scene", json={"preset": "invalid"})
        assert resp.status_code == 422


class TestSetWeather:
    def test_success(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            resp = client.post("/studio/weather", json={"type": "rain", "time_of_day": 20.0})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["state"]["weather"] == "rain"
        assert data["state"]["time_of_day"] == 20.0

    def test_ue_offline(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            resp = client.post("/studio/weather", json={"type": "snow"})
        data = resp.json()
        assert data["success"] is False
        assert data["state"]["weather"] == "clear"

    def test_invalid_time(self, client):
        resp = client.post("/studio/weather", json={"time_of_day": 30.0})
        assert resp.status_code == 422


class TestSetPrivacy:
    def test_success(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            resp = client.post("/studio/privacy", json={"level": 0.5})
        data = resp.json()
        assert data["success"] is True
        assert data["state"]["privacy_level"] == 0.5

    def test_ue_offline(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            resp = client.post("/studio/privacy", json={"level": 0.5})
        data = resp.json()
        assert data["success"] is False
        assert data["state"]["privacy_level"] == 0.0

    def test_invalid_level(self, client):
        resp = client.post("/studio/privacy", json={"level": 2.0})
        assert resp.status_code == 422


class TestSetLighting:
    def test_success(self, client, studio_manager):
        payload = {"key": 1.0, "fill": 0.5, "back": 0.3, "temperature": 6500.0}
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            resp = client.post("/studio/lighting", json=payload)
        data = resp.json()
        assert data["success"] is True
        assert data["state"]["lighting_key"] == 1.0
        assert data["state"]["lighting_temperature"] == 6500.0

    def test_ue_offline(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            resp = client.post("/studio/lighting", json={})
        data = resp.json()
        assert data["success"] is False
        # defaults unchanged
        assert data["state"]["lighting_key"] == 0.8


class TestSetCharacter:
    def test_action_success(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            resp = client.post("/studio/character", json={"action": "talking"})
        data = resp.json()
        assert data["success"] is True
        assert data["state"]["character_action"] == "talking"

    def test_expression_success(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            resp = client.post("/studio/character", json={"expression": "smile"})
        data = resp.json()
        assert data["success"] is True
        assert data["state"]["character_expression"] == "smile"

    def test_both_action_and_expression(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            resp = client.post("/studio/character", json={"action": "nodding", "expression": "smile"})
        data = resp.json()
        assert data["success"] is True
        assert data["state"]["character_action"] == "nodding"
        assert data["state"]["character_expression"] == "smile"

    def test_empty_request(self, client, studio_manager):
        # Empty request should succeed without hitting UE5
        resp = client.post("/studio/character", json={})
        data = resp.json()
        assert data["success"] is True

    def test_ue_offline(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            resp = client.post("/studio/character", json={"action": "waving"})
        data = resp.json()
        assert data["success"] is False
        assert data["state"]["character_action"] == "idle"

    def test_invalid_action(self, client):
        resp = client.post("/studio/character", json={"action": "dancing"})
        assert resp.status_code == 422

    def test_invalid_expression(self, client):
        resp = client.post("/studio/character", json={"expression": "angry"})
        assert resp.status_code == 422


class TestSetLightingValidation:
    def test_invalid_key_above_max(self, client):
        resp = client.post("/studio/lighting", json={"key": 1.5})
        assert resp.status_code == 422

    def test_invalid_temperature_below_min(self, client):
        resp = client.post("/studio/lighting", json={"temperature": 1000})
        assert resp.status_code == 422


class TestManagerNotInitialized:
    def test_503_on_get_status(self):
        app = FastAPI()
        app.include_router(router)
        set_studio_manager(None)
        c = TestClient(app)
        resp = c.get("/studio/status")
        assert resp.status_code == 503

    def test_503_on_get_presets(self):
        app = FastAPI()
        app.include_router(router)
        set_studio_manager(None)
        c = TestClient(app)
        resp = c.get("/studio/presets")
        assert resp.status_code == 503

    def test_503_on_post_scene(self):
        app = FastAPI()
        app.include_router(router)
        set_studio_manager(None)
        c = TestClient(app)
        resp = c.post("/studio/scene", json={"preset": "news_desk"})
        assert resp.status_code == 503


class TestResponseStructure:
    """Verify all expected fields are present in responses."""

    def test_status_response_has_all_fields(self, client):
        resp = client.get("/studio/status")
        data = resp.json()
        expected_fields = {
            "scene", "weather", "time_of_day", "privacy_level",
            "lighting_key", "lighting_fill", "lighting_back", "lighting_temperature",
            "character_action", "character_expression",
            "ue_connected", "ue_fps", "ue_gpu_usage", "pixel_streaming_url",
        }
        assert expected_fields == set(data.keys())

    def test_presets_response_has_all_fields(self, client):
        resp = client.get("/studio/presets")
        data = resp.json()
        expected_fields = {
            "scenes", "weather_types", "character_actions",
            "character_expressions", "lighting_presets",
        }
        assert expected_fields == set(data.keys())

    def test_command_response_has_all_fields(self, client, studio_manager):
        with patch.object(studio_manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            resp = client.post("/studio/privacy", json={"level": 0.5})
        data = resp.json()
        assert {"success", "message", "state"} == set(data.keys())
        assert isinstance(data["state"], dict)
        assert "scene" in data["state"]
