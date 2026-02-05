"""Creative mode data models for Remotion configuration."""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class CreativeStyle(str, Enum):
    """Subtitle animation style."""

    KARAOKE = "karaoke"
    POPUP = "popup"
    SLIDE = "slide"
    TYPEWRITER = "typewriter"
    CUSTOM = "custom"


class EntranceType(str, Enum):
    """Entrance animation type."""

    FADE_IN = "fadeIn"
    SLIDE_IN = "slideIn"
    BOUNCE = "bounce"
    TYPEWRITER = "typewriter"
    NONE = "none"


class ExitType(str, Enum):
    """Exit animation type."""

    FADE_OUT = "fadeOut"
    SLIDE_OUT = "slideOut"
    NONE = "none"


class EasingType(str, Enum):
    """Animation easing type."""

    LINEAR = "linear"
    EASE_IN = "easeIn"
    EASE_OUT = "easeOut"
    EASE_IN_OUT = "easeInOut"
    SPRING = "spring"


class SubtitlePosition(str, Enum):
    """Subtitle position on screen."""

    BOTTOM = "bottom"
    TOP = "top"
    CENTER = "center"


class WordHighlightConfig(BaseModel):
    """Word highlight configuration for karaoke style."""

    enabled: bool = False
    color: str = "#facc15"
    scale: float = 1.1
    duration: int = 15  # frames


class EntranceAnimation(BaseModel):
    """Entrance animation configuration."""

    type: EntranceType = EntranceType.FADE_IN
    duration: int = 10  # frames
    easing: EasingType = EasingType.EASE_OUT


class ExitAnimation(BaseModel):
    """Exit animation configuration."""

    type: ExitType = ExitType.FADE_OUT
    duration: int = 10  # frames
    easing: EasingType = EasingType.EASE_IN


class AnimationConfig(BaseModel):
    """Animation configuration."""

    entrance: EntranceAnimation = Field(default_factory=EntranceAnimation)
    wordHighlight: Optional[WordHighlightConfig] = None
    exit: ExitAnimation = Field(default_factory=ExitAnimation)


class GlobalConfig(BaseModel):
    """Global configuration for subtitles."""

    fontFamily: str = "Inter, system-ui, sans-serif"
    backgroundColor: str = "#1a2744"
    subtitlePosition: SubtitlePosition = SubtitlePosition.BOTTOM
    enFontSize: int = 32
    zhFontSize: int = 28
    enColor: str = "#ffffff"
    zhColor: str = "#facc15"
    fontWeight: str = "600"
    lineSpacing: int = 8


class SegmentOverride(BaseModel):
    """Per-segment animation override."""

    id: int
    overrides: Optional[Dict[str, Any]] = None


class RemotionConfig(BaseModel):
    """Full Remotion configuration."""

    version: str = "1.0"
    style: CreativeStyle = CreativeStyle.KARAOKE
    global_: GlobalConfig = Field(default_factory=GlobalConfig, alias="global")
    animation: AnimationConfig = Field(default_factory=AnimationConfig)
    segments: Optional[List[SegmentOverride]] = None

    class Config:
        populate_by_name = True


# ============ API Request/Response Models ============


class GenerateConfigRequest(BaseModel):
    """Request to generate RemotionConfig from natural language."""

    prompt: str
    style_preset: Optional[CreativeStyle] = None
    previous_config: Optional[RemotionConfig] = None


class GenerateConfigResponse(BaseModel):
    """Response with generated RemotionConfig."""

    config: RemotionConfig
    explanation: str
    tokens_used: int = 0
    cost_usd: float = 0.0


class SaveConfigRequest(BaseModel):
    """Request to save RemotionConfig to timeline."""

    config: RemotionConfig


class SaveConfigResponse(BaseModel):
    """Response after saving config."""

    timeline_id: str
    message: str


class GetConfigResponse(BaseModel):
    """Response with stored RemotionConfig."""

    timeline_id: str
    config: Optional[RemotionConfig] = None
    has_config: bool = False


# ============ Style Presets ============

STYLE_PRESETS: Dict[CreativeStyle, AnimationConfig] = {
    CreativeStyle.KARAOKE: AnimationConfig(
        entrance=EntranceAnimation(type=EntranceType.FADE_IN, duration=10, easing=EasingType.EASE_OUT),
        wordHighlight=WordHighlightConfig(enabled=True, color="#facc15", scale=1.1, duration=15),
        exit=ExitAnimation(type=ExitType.FADE_OUT, duration=10, easing=EasingType.EASE_IN),
    ),
    CreativeStyle.POPUP: AnimationConfig(
        entrance=EntranceAnimation(type=EntranceType.BOUNCE, duration=15, easing=EasingType.SPRING),
        wordHighlight=None,
        exit=ExitAnimation(type=ExitType.FADE_OUT, duration=10, easing=EasingType.EASE_IN),
    ),
    CreativeStyle.SLIDE: AnimationConfig(
        entrance=EntranceAnimation(type=EntranceType.SLIDE_IN, duration=12, easing=EasingType.EASE_OUT),
        wordHighlight=None,
        exit=ExitAnimation(type=ExitType.SLIDE_OUT, duration=12, easing=EasingType.EASE_IN),
    ),
    CreativeStyle.TYPEWRITER: AnimationConfig(
        entrance=EntranceAnimation(type=EntranceType.TYPEWRITER, duration=20, easing=EasingType.LINEAR),
        wordHighlight=None,
        exit=ExitAnimation(type=ExitType.FADE_OUT, duration=8, easing=EasingType.EASE_IN),
    ),
    CreativeStyle.CUSTOM: AnimationConfig(
        entrance=EntranceAnimation(type=EntranceType.FADE_IN, duration=10, easing=EasingType.EASE_OUT),
        wordHighlight=None,
        exit=ExitAnimation(type=ExitType.FADE_OUT, duration=10, easing=EasingType.EASE_IN),
    ),
}


def create_default_config(style: CreativeStyle = CreativeStyle.KARAOKE) -> RemotionConfig:
    """Create a default RemotionConfig with the specified style preset."""
    return RemotionConfig(
        version="1.0",
        style=style,
        global_=GlobalConfig(),
        animation=STYLE_PRESETS.get(style, STYLE_PRESETS[CreativeStyle.KARAOKE]),
    )
