"""Speech recognition worker using Whisper."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional
from loguru import logger

from app.config import settings
from app.models.transcript import Segment, Transcript

# Dedicated thread pool for CPU-bound model operations
_model_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="whisper")


class WhisperWorker:
    """Worker for speech recognition using faster-whisper."""

    def __init__(self):
        self.model = None
        self.model_name = settings.whisper_model
        self.device = settings.whisper_device
        self.compute_type = settings.whisper_compute_type
        self._loading = False

    def _load_model_sync(self):
        """Synchronous model loading (runs in thread pool)."""
        if self.model is None and not self._loading:
            self._loading = True
            try:
                from faster_whisper import WhisperModel

                logger.info(f"Loading Whisper model: {self.model_name}")
                self.model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                logger.info("Whisper model loaded")
            finally:
                self._loading = False

    async def _load_model(self):
        """Async model loading - runs in thread pool to avoid blocking event loop."""
        if self.model is None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(_model_executor, self._load_model_sync)

    def _transcribe_sync(self, audio_path: str, language: Optional[str]) -> tuple:
        """Synchronous transcription (runs in thread pool)."""
        segments_iter, info = self.model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            vad_filter=True,
        )
        # Consume iterator in thread to avoid blocking
        segments_list = list(segments_iter)
        return segments_list, info

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
        # Load model in thread pool (non-blocking)
        await self._load_model()

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing: {audio_path}")

        # Run transcription in thread pool (non-blocking)
        loop = asyncio.get_event_loop()
        segments_list, info = await loop.run_in_executor(
            _model_executor,
            self._transcribe_sync,
            str(audio_path),
            language,
        )

        detected_language = info.language
        logger.info(f"Detected language: {detected_language}")

        # Convert to our segment format
        segments: List[Segment] = []
        for segment in segments_list:
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
