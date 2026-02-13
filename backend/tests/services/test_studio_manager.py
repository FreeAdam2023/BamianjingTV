"""Tests for StudioManager service."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.models.studio import (
    CharacterAction,
    CharacterExpression,
    CharacterRequest,
    LightingPreset,
    LightingRequest,
    PrivacyRequest,
    ScenePreset,
    SceneRequest,
    ScreenContentRequest,
    ScreenContentType,
    StudioState,
    WeatherRequest,
    WeatherType,
)
from app.services.studio_manager import StudioManager


@pytest.fixture
def temp_state_file():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "studio_state.json"


@pytest.fixture
def manager(temp_state_file):
    return StudioManager(
        ue_base_url="http://fake-ue:30010",
        pixel_streaming_url="http://fake-ue:80",
        state_file=temp_state_file,
    )


class TestInit:
    def test_default_state(self, manager):
        state = manager.get_state()
        assert state.scene == ScenePreset.MODERN_OFFICE
        assert state.ue_connected is False
        assert state.pixel_streaming_url == "http://fake-ue:80"

    def test_loads_persisted_state(self, temp_state_file):
        data = StudioState(
            scene=ScenePreset.NEWS_DESK,
            privacy_level=0.7,
        ).model_dump(mode="json")
        temp_state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_state_file.write_text(json.dumps(data), encoding="utf-8")

        mgr = StudioManager(
            ue_base_url="http://fake-ue:30010",
            pixel_streaming_url="http://fake-ue:80",
            state_file=temp_state_file,
        )
        state = mgr.get_state()
        assert state.scene == ScenePreset.NEWS_DESK
        assert state.privacy_level == 0.7
        # pixel_streaming_url should come from constructor, not persisted file
        assert state.pixel_streaming_url == "http://fake-ue:80"

    def test_no_state_file(self):
        mgr = StudioManager(state_file=None)
        state = mgr.get_state()
        assert state.scene == ScenePreset.MODERN_OFFICE

    def test_corrupt_state_file_falls_back_to_defaults(self, temp_state_file):
        """_load_state except branch: corrupt JSON falls back to defaults."""
        temp_state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_state_file.write_text("{invalid json!!!", encoding="utf-8")

        mgr = StudioManager(
            ue_base_url="http://fake-ue:30010",
            pixel_streaming_url="http://fake-ue:80",
            state_file=temp_state_file,
        )
        state = mgr.get_state()
        assert state.scene == ScenePreset.MODERN_OFFICE  # defaults

    def test_invalid_state_data_falls_back_to_defaults(self, temp_state_file):
        """_load_state except branch: valid JSON but invalid model data."""
        temp_state_file.parent.mkdir(parents=True, exist_ok=True)
        temp_state_file.write_text(
            json.dumps({"scene": "nonexistent_scene"}),
            encoding="utf-8",
        )

        mgr = StudioManager(
            ue_base_url="http://fake-ue:30010",
            pixel_streaming_url="http://fake-ue:80",
            state_file=temp_state_file,
        )
        state = mgr.get_state()
        assert state.scene == ScenePreset.MODERN_OFFICE  # defaults


class TestGetPresets:
    def test_contains_all_enums(self, manager):
        presets = manager.get_presets()
        assert len(presets.scenes) == len(ScenePreset)
        assert len(presets.weather_types) == len(WeatherType)
        assert len(presets.character_actions) == len(CharacterAction)
        assert len(presets.character_expressions) == len(CharacterExpression)
        assert "interview" in presets.lighting_presets
        assert len(presets.screen_content_types) == len(ScreenContentType)
        assert "screen_capture" in presets.screen_content_types


class TestSetScene:
    @pytest.mark.asyncio
    async def test_success_updates_state(self, manager):
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            ok = await manager.set_scene(SceneRequest(preset=ScenePreset.NEWS_DESK))
        assert ok is True
        state = manager.get_state()
        assert state.scene == ScenePreset.NEWS_DESK
        assert state.ue_connected is True

    @pytest.mark.asyncio
    async def test_failure_keeps_old_state(self, manager):
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            ok = await manager.set_scene(SceneRequest(preset=ScenePreset.NEWS_DESK))
        assert ok is False
        state = manager.get_state()
        assert state.scene == ScenePreset.MODERN_OFFICE  # unchanged
        assert state.ue_connected is False

    @pytest.mark.asyncio
    async def test_persists_on_success(self, manager, temp_state_file):
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            await manager.set_scene(SceneRequest(preset=ScenePreset.CLASSROOM))
        assert temp_state_file.exists()
        data = json.loads(temp_state_file.read_text(encoding="utf-8"))
        assert data["scene"] == "classroom"


class TestSetWeather:
    @pytest.mark.asyncio
    async def test_success(self, manager):
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            ok = await manager.set_weather(WeatherRequest(type=WeatherType.RAIN, time_of_day=20.0))
        assert ok is True
        state = manager.get_state()
        assert state.weather == WeatherType.RAIN
        assert state.time_of_day == 20.0

    @pytest.mark.asyncio
    async def test_failure(self, manager):
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            ok = await manager.set_weather(WeatherRequest(type=WeatherType.SNOW))
        assert ok is False
        assert manager.get_state().weather == WeatherType.CLEAR


class TestSetPrivacy:
    @pytest.mark.asyncio
    async def test_success(self, manager):
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            ok = await manager.set_privacy(PrivacyRequest(level=0.75))
        assert ok is True
        assert manager.get_state().privacy_level == 0.75

    @pytest.mark.asyncio
    async def test_failure(self, manager):
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            ok = await manager.set_privacy(PrivacyRequest(level=0.75))
        assert ok is False
        assert manager.get_state().privacy_level == 0.0


class TestSetLighting:
    @pytest.mark.asyncio
    async def test_success(self, manager):
        req = LightingRequest(key=1.0, fill=0.5, back=0.3, temperature=6500.0)
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            ok = await manager.set_lighting(req)
        assert ok is True
        state = manager.get_state()
        assert state.lighting_key == 1.0
        assert state.lighting_temperature == 6500.0

    @pytest.mark.asyncio
    async def test_with_preset(self, manager):
        req = LightingRequest(preset=LightingPreset.DRAMATIC)
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True) as mock:
            await manager.set_lighting(req)
        call_payload = mock.call_args[0][1]
        assert call_payload["preset"] == "dramatic"

    @pytest.mark.asyncio
    async def test_failure(self, manager):
        req = LightingRequest(key=1.0)
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            ok = await manager.set_lighting(req)
        assert ok is False
        assert manager.get_state().lighting_key == 0.8  # default unchanged


class TestSetCharacter:
    @pytest.mark.asyncio
    async def test_action_only(self, manager):
        req = CharacterRequest(action=CharacterAction.TALKING)
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            ok = await manager.set_character(req)
        assert ok is True
        state = manager.get_state()
        assert state.character_action == CharacterAction.TALKING
        assert state.character_expression == CharacterExpression.NEUTRAL  # unchanged

    @pytest.mark.asyncio
    async def test_expression_only(self, manager):
        req = CharacterRequest(expression=CharacterExpression.SMILE)
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            ok = await manager.set_character(req)
        assert ok is True
        assert manager.get_state().character_expression == CharacterExpression.SMILE

    @pytest.mark.asyncio
    async def test_both_action_and_expression(self, manager):
        req = CharacterRequest(
            action=CharacterAction.TALKING,
            expression=CharacterExpression.SMILE,
        )
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True) as mock:
            ok = await manager.set_character(req)
        assert ok is True
        state = manager.get_state()
        assert state.character_action == CharacterAction.TALKING
        assert state.character_expression == CharacterExpression.SMILE
        # Verify both sent in payload
        payload = mock.call_args[0][1]
        assert payload["action"] == "talking"
        assert payload["expression"] == "smile"

    @pytest.mark.asyncio
    async def test_empty_request_skips_ue(self, manager):
        req = CharacterRequest()
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock) as mock:
            ok = await manager.set_character(req)
        assert ok is True
        mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_failure(self, manager):
        req = CharacterRequest(action=CharacterAction.WAVING)
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            ok = await manager.set_character(req)
        assert ok is False
        assert manager.get_state().character_action == CharacterAction.IDLE


class TestSetScreenContent:
    @pytest.mark.asyncio
    async def test_success(self, manager):
        req = ScreenContentRequest(
            content_type=ScreenContentType.WEB_URL,
            url="https://example.com",
            brightness=0.8,
        )
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            ok = await manager.set_screen_content(req)
        assert ok is True
        state = manager.get_state()
        assert state.screen_content_type == ScreenContentType.WEB_URL
        assert state.screen_url == "https://example.com"
        assert state.screen_brightness == 0.8

    @pytest.mark.asyncio
    async def test_failure_keeps_old_state(self, manager):
        req = ScreenContentRequest(content_type=ScreenContentType.SCREEN_CAPTURE)
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            ok = await manager.set_screen_content(req)
        assert ok is False
        state = manager.get_state()
        assert state.screen_content_type == ScreenContentType.OFF  # default unchanged

    @pytest.mark.asyncio
    async def test_off_clears_url(self, manager):
        # First set a URL
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            await manager.set_screen_content(ScreenContentRequest(
                content_type=ScreenContentType.WEB_URL,
                url="https://example.com",
            ))
        assert manager.get_state().screen_url == "https://example.com"

        # Now turn off — url should be None
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            await manager.set_screen_content(ScreenContentRequest(
                content_type=ScreenContentType.OFF,
            ))
        state = manager.get_state()
        assert state.screen_content_type == ScreenContentType.OFF
        assert state.screen_url is None

    @pytest.mark.asyncio
    async def test_payload_sent_to_ue(self, manager):
        req = ScreenContentRequest(
            content_type=ScreenContentType.CUSTOM_IMAGE,
            url="https://example.com/img.png",
            brightness=0.5,
        )
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True) as mock:
            await manager.set_screen_content(req)
        call_payload = mock.call_args[0][1]
        assert call_payload["content_type"] == "custom_image"
        assert call_payload["url"] == "https://example.com/img.png"
        assert call_payload["brightness"] == 0.5

    @pytest.mark.asyncio
    async def test_persists_on_success(self, manager, temp_state_file):
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            await manager.set_screen_content(ScreenContentRequest(
                content_type=ScreenContentType.SCREEN_CAPTURE,
                brightness=0.6,
            ))
        assert temp_state_file.exists()
        data = json.loads(temp_state_file.read_text(encoding="utf-8"))
        assert data["screen_content_type"] == "screen_capture"
        assert data["screen_brightness"] == 0.6


class TestForwardToUE:
    @pytest.mark.asyncio
    async def test_connect_error(self, manager):
        # Real call to unreachable host
        result = await manager._forward_to_ue("/test", {"foo": "bar"})
        assert result is False

    @pytest.mark.asyncio
    async def test_success_response(self, manager):
        mock_response = httpx.Response(200, json={"ok": True})
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await manager._forward_to_ue("/test", {"foo": "bar"})
        assert result is True

    @pytest.mark.asyncio
    async def test_error_response(self, manager):
        mock_response = httpx.Response(500, text="error")
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await manager._forward_to_ue("/test", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_generic_exception(self, manager):
        """Covers the generic except branch (non-ConnectError)."""
        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock, side_effect=RuntimeError("boom")
        ):
            result = await manager._forward_to_ue("/test", {})
        assert result is False


class TestGetClient:
    @pytest.mark.asyncio
    async def test_reuses_existing_client(self, manager):
        client1 = await manager._get_client()
        client2 = await manager._get_client()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_recreates_closed_client(self, manager):
        client1 = await manager._get_client()
        await client1.aclose()
        assert client1.is_closed
        client2 = await manager._get_client()
        assert client2 is not client1
        assert not client2.is_closed
        await client2.aclose()


class TestStateIsolation:
    def test_get_state_returns_copy(self, manager):
        """Mutating the returned state should not affect internal state."""
        state = manager.get_state()
        state.scene = ScenePreset.CLASSROOM
        state.privacy_level = 0.99
        # Internal state unchanged
        internal = manager.get_state()
        assert internal.scene == ScenePreset.MODERN_OFFICE
        assert internal.privacy_level == 0.0


class TestSaveStateFailure:
    @pytest.mark.asyncio
    async def test_save_failure_does_not_crash(self, tmp_path):
        """_save_state except branch: read-only path should not raise."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        state_file = readonly_dir / "subdir" / "state.json"
        mgr = StudioManager(
            ue_base_url="http://fake-ue:30010",
            pixel_streaming_url="http://fake-ue:80",
            state_file=state_file,
        )
        # Make dir read-only so write fails
        readonly_dir.chmod(0o444)
        try:
            with patch.object(mgr, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
                # Should succeed even if save fails
                ok = await mgr.set_privacy(PrivacyRequest(level=0.5))
            assert ok is True
            assert mgr.get_state().privacy_level == 0.5
        finally:
            readonly_dir.chmod(0o755)

    @pytest.mark.asyncio
    async def test_failure_does_not_persist(self, manager, temp_state_file):
        """Failure should not write state file."""
        # First succeed to create file
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            await manager.set_scene(SceneRequest(preset=ScenePreset.NEWS_DESK))
        data_before = json.loads(temp_state_file.read_text(encoding="utf-8"))
        assert data_before["scene"] == "news_desk"

        # Now fail — file should keep news_desk, not change to classroom
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            await manager.set_scene(SceneRequest(preset=ScenePreset.CLASSROOM))
        data_after = json.loads(temp_state_file.read_text(encoding="utf-8"))
        assert data_after["scene"] == "news_desk"  # unchanged


class TestSequentialOperations:
    @pytest.mark.asyncio
    async def test_success_then_failure_retains_first_change(self, manager):
        """First success should be retained after a second failure."""
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            await manager.set_scene(SceneRequest(preset=ScenePreset.NEWS_DESK))
        assert manager.get_state().scene == ScenePreset.NEWS_DESK
        assert manager.get_state().ue_connected is True

        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=False):
            await manager.set_privacy(PrivacyRequest(level=0.5))
        # Scene still news_desk, privacy unchanged, ue_connected now False
        state = manager.get_state()
        assert state.scene == ScenePreset.NEWS_DESK
        assert state.privacy_level == 0.0
        assert state.ue_connected is False

    @pytest.mark.asyncio
    async def test_multiple_successes_accumulate(self, manager):
        """Multiple successful commands should all be reflected in state."""
        with patch.object(manager, "_forward_to_ue", new_callable=AsyncMock, return_value=True):
            await manager.set_scene(SceneRequest(preset=ScenePreset.CLASSROOM))
            await manager.set_weather(WeatherRequest(type=WeatherType.RAIN, time_of_day=8.0))
            await manager.set_privacy(PrivacyRequest(level=0.5))
            await manager.set_character(CharacterRequest(
                action=CharacterAction.TALKING,
                expression=CharacterExpression.SMILE,
            ))

        state = manager.get_state()
        assert state.scene == ScenePreset.CLASSROOM
        assert state.weather == WeatherType.RAIN
        assert state.time_of_day == 8.0
        assert state.privacy_level == 0.5
        assert state.character_action == CharacterAction.TALKING
        assert state.character_expression == CharacterExpression.SMILE
        assert state.ue_connected is True


class TestClose:
    @pytest.mark.asyncio
    async def test_close_without_client(self, manager):
        await manager.close()  # should not raise

    @pytest.mark.asyncio
    async def test_close_with_client(self, manager):
        # Force client creation
        manager._client = httpx.AsyncClient()
        await manager.close()
        assert manager._client.is_closed
