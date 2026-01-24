"""Pipeline and Target configuration models for MirrorFlow v2."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class PipelineType(str, Enum):
    """Pipeline type enum."""
    FULL_DUB = "full_dub"           # Full dubbing + subtitles
    SUBTITLE_ONLY = "subtitle"      # Subtitles only (keep original audio)
    DUB_NO_SUB = "dub_no_sub"       # Dubbing only (no subtitles)
    SHORTS = "shorts"               # Short video clips
    AUDIO_ONLY = "audio"            # Audio only


class SubtitleStyle(str, Enum):
    """Subtitle style options."""
    BILINGUAL = "bilingual"         # English (top) + Chinese (bottom)
    CHINESE_ONLY = "chinese_only"   # Chinese only (bottom)
    ENGLISH_ONLY = "english_only"   # English only (bottom)
    NONE = "none"                   # No subtitles


class TargetType(str, Enum):
    """Target type for publishing."""
    YOUTUBE = "youtube"
    LOCAL = "local"
    S3 = "s3"
    FTP = "ftp"


class TargetConfig(BaseModel):
    """Publishing target configuration."""
    target_type: TargetType = Field(..., description="Target type: youtube, local, s3, etc.")
    target_id: str = Field(..., description="YouTube channel ID or path")
    display_name: str = Field(..., description="Display name, e.g., 'Chinese Channel'")

    # YouTube specific
    privacy_status: str = Field(default="private", description="YouTube privacy: private, unlisted, public")
    playlist_id: Optional[str] = Field(default=None, description="YouTube playlist ID")

    # General config
    auto_publish: bool = Field(default=False, description="Auto-publish after processing")
    config: dict = Field(default_factory=dict, description="Additional target-specific config")


class PipelineConfig(BaseModel):
    """Pipeline configuration."""
    pipeline_id: str = Field(..., description="Unique ID, e.g., 'zh_main', 'ja_channel', 'shorts'")
    pipeline_type: PipelineType = Field(..., description="Pipeline type")
    display_name: str = Field(..., description="Display name, e.g., 'Chinese Main Channel'")

    # Processing configuration
    target_language: str = Field(default="zh", description="Target language code")
    steps: List[str] = Field(
        default_factory=lambda: ["download", "transcribe", "diarize", "translate", "tts", "mux"],
        description="Processing steps to execute"
    )

    # Audio/Video processing options
    enable_dubbing: bool = Field(default=True, description="Enable TTS dubbing")
    keep_original_audio: bool = Field(default=False, description="Mix original audio as background")
    original_audio_volume: float = Field(default=0.1, description="Original audio volume when mixing")

    # Subtitle options
    subtitle_style: SubtitleStyle = Field(default=SubtitleStyle.BILINGUAL, description="Subtitle style")
    use_traditional_chinese: bool = Field(default=True, description="Use Traditional Chinese (繁體)")
    burn_subtitles: bool = Field(default=True, description="Burn subtitles into video")

    # Content generation configuration
    generate_thumbnail: bool = Field(default=True, description="Generate AI thumbnail")
    generate_content: bool = Field(default=True, description="Generate title/description/tags")

    # Target configuration
    target: TargetConfig = Field(..., description="Publishing target")

    enabled: bool = Field(default=True, description="Whether pipeline is enabled")
    created_at: datetime = Field(default_factory=datetime.now)


class PipelineCreate(BaseModel):
    """Request model for creating a new pipeline."""
    pipeline_id: str
    pipeline_type: PipelineType
    display_name: str
    target_language: str = "zh"
    steps: List[str] = Field(
        default_factory=lambda: ["download", "transcribe", "diarize", "translate", "tts", "mux"]
    )
    # Audio/Video options
    enable_dubbing: bool = True
    keep_original_audio: bool = False
    original_audio_volume: float = 0.1
    # Subtitle options
    subtitle_style: SubtitleStyle = SubtitleStyle.BILINGUAL
    use_traditional_chinese: bool = True
    burn_subtitles: bool = True
    # Content generation
    generate_thumbnail: bool = True
    generate_content: bool = True
    target: TargetConfig
    enabled: bool = True


class PipelineUpdate(BaseModel):
    """Request model for updating a pipeline."""
    display_name: Optional[str] = None
    target_language: Optional[str] = None
    steps: Optional[List[str]] = None
    enable_dubbing: Optional[bool] = None
    keep_original_audio: Optional[bool] = None
    original_audio_volume: Optional[float] = None
    subtitle_style: Optional[SubtitleStyle] = None
    use_traditional_chinese: Optional[bool] = None
    burn_subtitles: Optional[bool] = None
    generate_thumbnail: Optional[bool] = None
    generate_content: Optional[bool] = None
    target: Optional[TargetConfig] = None
    enabled: Optional[bool] = None


# Default pipeline templates
DEFAULT_PIPELINES = {
    # Full dubbing with bilingual subtitles (Traditional Chinese)
    "default_zh": PipelineConfig(
        pipeline_id="default_zh",
        pipeline_type=PipelineType.FULL_DUB,
        display_name="中文配音+双语字幕",
        target_language="zh",
        enable_dubbing=True,
        keep_original_audio=False,
        subtitle_style=SubtitleStyle.BILINGUAL,
        use_traditional_chinese=True,
        burn_subtitles=True,
        target=TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local Output",
        ),
    ),
    # Subtitles only (keep original English audio)
    "subtitle_only": PipelineConfig(
        pipeline_id="subtitle_only",
        pipeline_type=PipelineType.SUBTITLE_ONLY,
        display_name="仅字幕(保留原声)",
        target_language="zh",
        enable_dubbing=False,
        keep_original_audio=True,
        original_audio_volume=1.0,
        subtitle_style=SubtitleStyle.BILINGUAL,
        use_traditional_chinese=True,
        burn_subtitles=True,
        steps=["download", "transcribe", "diarize", "translate", "mux"],  # No TTS
        target=TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local Output",
        ),
    ),
    # Dubbing + mixed original audio (for background music/effects)
    "dub_with_bg": PipelineConfig(
        pipeline_id="dub_with_bg",
        pipeline_type=PipelineType.FULL_DUB,
        display_name="配音+原声背景",
        target_language="zh",
        enable_dubbing=True,
        keep_original_audio=True,
        original_audio_volume=0.15,
        subtitle_style=SubtitleStyle.BILINGUAL,
        use_traditional_chinese=True,
        burn_subtitles=True,
        target=TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local Output",
        ),
    ),
}
