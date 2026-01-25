"""Worker modules for Hardcore Player pipeline."""

from .download import DownloadWorker
from .whisper import WhisperWorker
from .diarization import DiarizationWorker
from .translation import TranslationWorker
from .tts import TTSWorker  # Optional: TTS dubbing
from .export import ExportWorker
from .youtube import YouTubeWorker

__all__ = [
    "DownloadWorker",
    "WhisperWorker",
    "DiarizationWorker",
    "TranslationWorker",
    "TTSWorker",
    "ExportWorker",
    "YouTubeWorker",
]
