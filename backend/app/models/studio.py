"""Virtual Studio data models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ScenePreset(str, Enum):
    """Available scene presets."""
    MODERN_OFFICE = "modern_office"
    NEWS_DESK = "news_desk"
    PODCAST_STUDIO = "podcast_studio"
    CLASSROOM = "classroom"
    HOME_STUDY = "home_study"


class WeatherType(str, Enum):
    """Weather types for the virtual environment."""
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    SNOW = "snow"
    NIGHT = "night"


class CharacterAction(str, Enum):
    """Available character actions."""
    IDLE = "idle"
    TALKING = "talking"
    NODDING = "nodding"
    THINKING = "thinking"
    WAVING = "waving"
    WRITING = "writing"


class CharacterExpression(str, Enum):
    """Available character expressions."""
    NEUTRAL = "neutral"
    SMILE = "smile"
    SERIOUS = "serious"
    SURPRISED = "surprised"


class LightingPreset(str, Enum):
    """Lighting presets."""
    INTERVIEW = "interview"
    DRAMATIC = "dramatic"
    SOFT = "soft"
    NATURAL = "natural"


class ScreenContentType(str, Enum):
    """Content types for in-scene monitors."""
    SCREEN_CAPTURE = "screen_capture"
    WEB_URL = "web_url"
    CUSTOM_IMAGE = "custom_image"
    OFF = "off"


# ============ Request Models ============


class SceneRequest(BaseModel):
    """Request to change scene preset."""
    preset: ScenePreset


class WeatherRequest(BaseModel):
    """Request to change weather/time."""
    type: WeatherType = WeatherType.CLEAR
    time_of_day: float = Field(default=14.0, ge=0.0, le=24.0, description="Hour of day (0-24)")


class PrivacyRequest(BaseModel):
    """Request to set privacy blur level."""
    level: float = Field(default=0.0, ge=0.0, le=1.0, description="0.0=clear, 1.0=fully blurred")


class LightingRequest(BaseModel):
    """Request to adjust lighting."""
    key: float = Field(default=0.8, ge=0.0, le=1.0, description="Key light intensity")
    fill: float = Field(default=0.4, ge=0.0, le=1.0, description="Fill light intensity")
    back: float = Field(default=0.6, ge=0.0, le=1.0, description="Back light intensity")
    temperature: float = Field(default=5500.0, ge=2000.0, le=10000.0, description="Color temperature (Kelvin)")
    preset: Optional[LightingPreset] = None


class CharacterRequest(BaseModel):
    """Request to change character action/expression."""
    action: Optional[CharacterAction] = None
    expression: Optional[CharacterExpression] = None


class ScreenContentRequest(BaseModel):
    """Request to change monitor screen content."""
    content_type: ScreenContentType = ScreenContentType.SCREEN_CAPTURE
    url: Optional[str] = Field(default=None, description="URL for web_url or custom_image types")
    brightness: float = Field(default=1.0, ge=0.0, le=1.0, description="Screen brightness (0=off, 1=full)")


# ============ State / Response Models ============


class StudioState(BaseModel):
    """Current state of the virtual studio."""
    scene: ScenePreset = ScenePreset.MODERN_OFFICE
    weather: WeatherType = WeatherType.CLEAR
    time_of_day: float = 14.0
    privacy_level: float = 0.0
    lighting_key: float = 0.8
    lighting_fill: float = 0.4
    lighting_back: float = 0.6
    lighting_temperature: float = 5500.0
    character_action: CharacterAction = CharacterAction.IDLE
    character_expression: CharacterExpression = CharacterExpression.NEUTRAL
    screen_content_type: ScreenContentType = ScreenContentType.OFF
    screen_url: Optional[str] = None
    screen_brightness: float = 1.0
    ue_connected: bool = False
    ue_fps: Optional[float] = None
    ue_gpu_usage: Optional[float] = None
    pixel_streaming_url: str = ""


class StudioPresets(BaseModel):
    """Available presets for all categories."""
    scenes: list[str]
    weather_types: list[str]
    character_actions: list[str]
    character_expressions: list[str]
    lighting_presets: list[str]
    screen_content_types: list[str]


class StudioCommandResponse(BaseModel):
    """Response after sending a control command."""
    success: bool
    message: str
    state: StudioState
