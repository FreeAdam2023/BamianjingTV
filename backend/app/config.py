"""Configuration settings for SceneMind.

Learning video factory: transcription, translation, and bilingual subtitles.
"""

import json
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    jobs_dir: Path = Path("jobs")
    data_dir: Path = Path("data")  # v2: Base data directory
    models_cache_dir: Path = Path(".cache/models")

    @property
    def sources_file(self) -> Path:
        """Path to sources.json file."""
        return self.data_dir / "sources.json"

    @property
    def pipelines_file(self) -> Path:
        """Path to pipelines.json file."""
        return self.data_dir / "pipelines.json"

    @property
    def items_dir(self) -> Path:
        """Path to items directory."""
        return self.data_dir / "items"

    @property
    def timelines_dir(self) -> Path:
        """Path to timelines directory."""
        return self.data_dir / "timelines"

    @property
    def scenemind_dir(self) -> Path:
        """SceneMind data directory."""
        return self.data_dir / "scenemind"

    @property
    def scenemind_sessions_dir(self) -> Path:
        """SceneMind sessions directory."""
        return self.scenemind_dir / "sessions"

    @property
    def scenemind_frames_dir(self) -> Path:
        """SceneMind frames directory."""
        return self.scenemind_dir / "frames"

    @property
    def scenemind_videos_dir(self) -> Path:
        """SceneMind uploaded videos directory."""
        return self.scenemind_dir / "videos"

    @property
    def music_dir(self) -> Path:
        """Path to music directory."""
        return self.data_dir / "music"

    # Music generation settings
    music_device: str = "cuda"

    # Upload settings
    max_upload_size_mb: int = 4096  # 4GB max upload

    # Whisper settings
    whisper_model: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    # Diarization settings
    hf_token: str = ""  # HuggingFace token for pyannote.audio
    diarization_device: str = "cuda"

    # TTS settings (optional, for dubbing mode)
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_device: str = "cuda"

    # Translation LLM settings (supports OpenAI, Grok, Azure, or any OpenAI-compatible API)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.x.ai/v1"  # Default to Grok
    llm_model: str = "grok-4-fast-non-reasoning"  # Default model

    # Image generation settings (for thumbnails)
    # Set to empty string to disable thumbnail generation
    # Grok: "grok-2-image" (may not be available for all accounts)
    # OpenAI: "dall-e-3"
    image_model: str = ""  # Empty = disabled by default

    # Legacy Azure settings (only used if llm_base_url contains "azure")
    azure_api_version: str = "2024-12-01-preview"
    azure_deployment: str = ""

    @property
    def is_azure(self) -> bool:
        """Check if using Azure OpenAI."""
        return "azure" in self.llm_base_url.lower()

    @property
    def azure_deployment_name(self) -> str:
        """Get Azure deployment name from config or URL."""
        if self.azure_deployment:
            return self.azure_deployment
        if "/deployments/" in self.llm_base_url:
            parts = self.llm_base_url.split("/deployments/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
        return self.llm_model

    # Video settings
    ffmpeg_nvenc: bool = True
    max_video_duration: int = 7200  # 2 hours in seconds

    # Queue settings
    max_concurrent_jobs: int = 2  # Max concurrent job processing (adjust based on GPU memory)

    # YouTube settings
    youtube_credentials_file: str = "credentials/youtube_oauth.json"
    youtube_token_file: str = "credentials/youtube_token.pickle"

    # Cleanup settings (auto-delete old files to save disk space)
    cleanup_enabled: bool = False  # Enable scheduled cleanup
    cleanup_retention_days: int = 30  # Keep files for N days
    cleanup_videos_only: bool = True  # Only delete videos, keep metadata
    cleanup_schedule_hour: int = 3  # Hour of day to run (0-23, default 3 AM)

    # TomTrove API settings (for word cards and entity cards)
    tomtrove_api_url: str = "http://localhost:8000/api/v1/public"
    tomtrove_api_key: str = ""  # Set via TOMTROVE_API_KEY env var

    # Azure Translator settings (for subtitle translation - fast and consistent)
    azure_translator_key: str = ""  # Set via AZURE_TRANSLATOR_KEY env var
    azure_translator_endpoint: str = "https://api.cognitive.microsofttranslator.com/"
    azure_translator_region: str = "eastasia"  # Region where resource was created

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8001
    debug: bool = False

    # Frontend settings
    frontend_url: str = "http://localhost:3001"
    frontend_dir: Path = Path("../frontend")  # Path to frontend directory for Remotion
    cors_origins: List[str] = ["http://localhost:3001", "http://127.0.0.1:3001"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from JSON string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # If not valid JSON, treat as comma-separated list
                return [origin.strip() for origin in v.split(",")]
        return v



settings = Settings()


def get_config() -> Settings:
    """Get the application settings.

    This function allows for dependency injection in tests.
    """
    return settings


# Ensure directories exist
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.items_dir.mkdir(parents=True, exist_ok=True)
settings.timelines_dir.mkdir(parents=True, exist_ok=True)
settings.models_cache_dir.mkdir(parents=True, exist_ok=True)
settings.scenemind_sessions_dir.mkdir(parents=True, exist_ok=True)
settings.scenemind_frames_dir.mkdir(parents=True, exist_ok=True)
settings.scenemind_videos_dir.mkdir(parents=True, exist_ok=True)
settings.music_dir.mkdir(parents=True, exist_ok=True)
