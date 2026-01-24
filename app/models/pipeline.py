"""Pipeline and Target configuration models for MirrorFlow v2."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class PipelineType(str, Enum):
    """Pipeline type enum."""
    FULL_DUB = "full_dub"           # Full dubbing
    SUBTITLE_ONLY = "subtitle"      # Subtitles only
    SHORTS = "shorts"               # Short video clips
    AUDIO_ONLY = "audio"            # Audio only


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
    generate_thumbnail: bool = True
    generate_content: bool = True
    target: TargetConfig
    enabled: bool = True


class PipelineUpdate(BaseModel):
    """Request model for updating a pipeline."""
    display_name: Optional[str] = None
    target_language: Optional[str] = None
    steps: Optional[List[str]] = None
    generate_thumbnail: Optional[bool] = None
    generate_content: Optional[bool] = None
    target: Optional[TargetConfig] = None
    enabled: Optional[bool] = None


# Default pipeline templates
DEFAULT_PIPELINES = {
    "default_zh": PipelineConfig(
        pipeline_id="default_zh",
        pipeline_type=PipelineType.FULL_DUB,
        display_name="Default Chinese",
        target_language="zh",
        target=TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local Output",
        ),
    ),
}
