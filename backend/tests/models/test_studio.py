"""Tests for Virtual Studio data models."""

import pytest
from pydantic import ValidationError

from app.models.studio import (
    CharacterAction,
    CharacterExpression,
    CharacterRequest,
    LightingPreset,
    LightingRequest,
    PrivacyRequest,
    ScenePreset,
    SceneRequest,
    StudioCommandResponse,
    StudioPresets,
    StudioState,
    WeatherRequest,
    WeatherType,
)


class TestEnums:
    """Test enum values and membership."""

    def test_scene_presets(self):
        assert ScenePreset.MODERN_OFFICE == "modern_office"
        assert ScenePreset.NEWS_DESK == "news_desk"
        assert len(ScenePreset) == 4

    def test_weather_types(self):
        assert WeatherType.CLEAR == "clear"
        assert WeatherType.NIGHT == "night"
        assert len(WeatherType) == 5

    def test_character_actions(self):
        assert CharacterAction.IDLE == "idle"
        assert len(CharacterAction) == 6

    def test_character_expressions(self):
        assert CharacterExpression.NEUTRAL == "neutral"
        assert len(CharacterExpression) == 4

    def test_lighting_presets(self):
        assert LightingPreset.INTERVIEW == "interview"
        assert len(LightingPreset) == 4


class TestSceneRequest:
    def test_valid(self):
        req = SceneRequest(preset=ScenePreset.NEWS_DESK)
        assert req.preset == ScenePreset.NEWS_DESK

    def test_from_string(self):
        req = SceneRequest(preset="podcast_studio")
        assert req.preset == ScenePreset.PODCAST_STUDIO

    def test_invalid_preset(self):
        with pytest.raises(ValidationError):
            SceneRequest(preset="nonexistent")


class TestWeatherRequest:
    def test_defaults(self):
        req = WeatherRequest()
        assert req.type == WeatherType.CLEAR
        assert req.time_of_day == 14.0

    def test_custom(self):
        req = WeatherRequest(type=WeatherType.RAIN, time_of_day=20.5)
        assert req.type == WeatherType.RAIN
        assert req.time_of_day == 20.5

    def test_time_of_day_bounds(self):
        WeatherRequest(time_of_day=0.0)
        WeatherRequest(time_of_day=24.0)
        with pytest.raises(ValidationError):
            WeatherRequest(time_of_day=-1.0)
        with pytest.raises(ValidationError):
            WeatherRequest(time_of_day=25.0)

    def test_invalid_weather_type(self):
        with pytest.raises(ValidationError):
            WeatherRequest(type="tornado")


class TestPrivacyRequest:
    def test_defaults(self):
        req = PrivacyRequest()
        assert req.level == 0.0

    def test_bounds(self):
        PrivacyRequest(level=0.0)
        PrivacyRequest(level=1.0)
        with pytest.raises(ValidationError):
            PrivacyRequest(level=-0.1)
        with pytest.raises(ValidationError):
            PrivacyRequest(level=1.1)


class TestLightingRequest:
    def test_defaults(self):
        req = LightingRequest()
        assert req.key == 0.8
        assert req.fill == 0.4
        assert req.back == 0.6
        assert req.temperature == 5500.0
        assert req.preset is None

    def test_with_preset(self):
        req = LightingRequest(preset=LightingPreset.DRAMATIC)
        assert req.preset == LightingPreset.DRAMATIC

    def test_temperature_bounds(self):
        LightingRequest(temperature=2000.0)
        LightingRequest(temperature=10000.0)
        with pytest.raises(ValidationError):
            LightingRequest(temperature=1999.0)
        with pytest.raises(ValidationError):
            LightingRequest(temperature=10001.0)

    def test_intensity_bounds(self):
        with pytest.raises(ValidationError):
            LightingRequest(key=1.5)
        with pytest.raises(ValidationError):
            LightingRequest(fill=-0.1)
        with pytest.raises(ValidationError):
            LightingRequest(back=2.0)


class TestCharacterRequest:
    def test_empty(self):
        req = CharacterRequest()
        assert req.action is None
        assert req.expression is None

    def test_action_only(self):
        req = CharacterRequest(action=CharacterAction.TALKING)
        assert req.action == CharacterAction.TALKING
        assert req.expression is None

    def test_expression_only(self):
        req = CharacterRequest(expression=CharacterExpression.SMILE)
        assert req.expression == CharacterExpression.SMILE
        assert req.action is None

    def test_both(self):
        req = CharacterRequest(
            action=CharacterAction.NODDING,
            expression=CharacterExpression.SMILE,
        )
        assert req.action == CharacterAction.NODDING
        assert req.expression == CharacterExpression.SMILE

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            CharacterRequest(action="dancing")

    def test_invalid_expression(self):
        with pytest.raises(ValidationError):
            CharacterRequest(expression="angry")


class TestStudioState:
    def test_defaults(self):
        state = StudioState()
        assert state.scene == ScenePreset.MODERN_OFFICE
        assert state.weather == WeatherType.CLEAR
        assert state.time_of_day == 14.0
        assert state.privacy_level == 0.0
        assert state.ue_connected is False
        assert state.pixel_streaming_url == ""

    def test_serialization_roundtrip(self):
        state = StudioState(
            scene=ScenePreset.NEWS_DESK,
            weather=WeatherType.RAIN,
            privacy_level=0.5,
            ue_connected=True,
            pixel_streaming_url="http://test:80",
        )
        data = state.model_dump(mode="json")
        restored = StudioState(**data)
        assert restored.scene == ScenePreset.NEWS_DESK
        assert restored.weather == WeatherType.RAIN
        assert restored.privacy_level == 0.5
        assert restored.pixel_streaming_url == "http://test:80"


class TestStudioPresets:
    def test_structure(self):
        presets = StudioPresets(
            scenes=["a"],
            weather_types=["b"],
            character_actions=["c"],
            character_expressions=["d"],
            lighting_presets=["e"],
        )
        assert presets.scenes == ["a"]


class TestStudioCommandResponse:
    def test_success(self):
        resp = StudioCommandResponse(
            success=True,
            message="OK",
            state=StudioState(),
        )
        assert resp.success is True

    def test_failure(self):
        resp = StudioCommandResponse(
            success=False,
            message="UE5 unreachable",
            state=StudioState(),
        )
        assert resp.success is False
