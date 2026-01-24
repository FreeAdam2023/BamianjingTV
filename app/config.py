"""Configuration settings for MirrorFlow."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Paths
    jobs_dir: Path = Path("jobs")
    models_cache_dir: Path = Path(".cache/models")

    # Whisper settings
    whisper_model: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    # Diarization settings
    hf_token: str = ""  # HuggingFace token for pyannote.audio
    diarization_device: str = "cuda"

    # Translation settings
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    translation_model: str = "gpt-4o-mini"

    # TTS settings
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_device: str = "cuda"

    # Video settings
    ffmpeg_nvenc: bool = True
    max_video_duration: int = 7200  # 2 hours in seconds

    # YouTube settings
    youtube_credentials_file: str = "credentials/youtube_oauth.json"
    youtube_token_file: str = "credentials/youtube_token.json"

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure directories exist
settings.jobs_dir.mkdir(parents=True, exist_ok=True)
settings.models_cache_dir.mkdir(parents=True, exist_ok=True)
