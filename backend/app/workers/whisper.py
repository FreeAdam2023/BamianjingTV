"""Speech recognition worker using Whisper."""

from pathlib import Path
from typing import List, Optional
from loguru import logger

from app.config import settings
from app.models.transcript import Segment, Transcript


class WhisperWorker:
    """Worker for speech recognition using faster-whisper."""

    def __init__(self):
        self.model = None
        self.model_name = settings.whisper_model
        self.device = settings.whisper_device
        self.compute_type = settings.whisper_compute_type

    def _load_model(self):
        """Lazy load the Whisper model."""
        if self.model is None:
            from faster_whisper import WhisperModel

            logger.info(f"Loading Whisper model: {self.model_name}")
            self.model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("Whisper model loaded")

    async def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> Transcript:
        """
        Transcribe audio file.

        Args:
            audio_path: Path to audio file (WAV recommended)
            language: Source language code (auto-detect if None)

        Returns:
            Transcript with timestamped segments
        """
        self._load_model()

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing: {audio_path}")

        # Transcribe with word timestamps for better alignment
        segments_iter, info = self.model.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,
            vad_filter=True,  # Filter out non-speech
        )

        detected_language = info.language
        logger.info(f"Detected language: {detected_language}")

        # Convert to our segment format
        segments: List[Segment] = []
        for segment in segments_iter:
            segments.append(
                Segment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                )
            )

        logger.info(f"Transcribed {len(segments)} segments")

        return Transcript(
            language=detected_language,
            segments=segments,
        )

    async def save_transcript(
        self,
        transcript: Transcript,
        output_path: Path,
    ) -> None:
        """Save transcript to JSON file."""
        import json

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(transcript.model_dump(), f, ensure_ascii=False, indent=2)

        logger.info(f"Transcript saved to: {output_path}")
