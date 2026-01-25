"""Speaker diarization worker using pyannote.audio."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional
from loguru import logger

from app.config import settings
from app.models.transcript import (
    Segment,
    DiarizedSegment,
    Transcript,
    DiarizedTranscript,
)

# Dedicated thread pool for CPU-bound model operations
_diarization_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="diarize")


class DiarizationWorker:
    """Worker for speaker diarization using pyannote.audio."""

    def __init__(self):
        self.pipeline = None
        self.hf_token = settings.hf_token
        self.device = settings.diarization_device
        self._loading = False

    def _load_pipeline_sync(self):
        """Synchronous pipeline loading (runs in thread pool)."""
        if self.pipeline is None and not self._loading:
            self._loading = True
            try:
                from pyannote.audio import Pipeline
                import torch

                if not self.hf_token:
                    raise ValueError(
                        "HuggingFace token required for pyannote.audio. "
                        "Set HF_TOKEN environment variable."
                    )

                logger.info("Loading diarization pipeline...")
                self.pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    token=self.hf_token,
                )

                # Move to GPU if available
                if self.device == "cuda" and torch.cuda.is_available():
                    self.pipeline.to(torch.device("cuda"))

                logger.info("Diarization pipeline loaded")
            finally:
                self._loading = False

    async def _load_pipeline(self):
        """Async pipeline loading - runs in thread pool to avoid blocking event loop."""
        if self.pipeline is None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(_diarization_executor, self._load_pipeline_sync)

    def _diarize_sync(self, audio_path: str, num_speakers: Optional[int]) -> List[dict]:
        """Synchronous diarization (runs in thread pool)."""
        diarization = self.pipeline(
            audio_path,
            num_speakers=num_speakers,
        )

        # Convert to list of segments
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker,
            })
        return segments

    async def diarize(
        self,
        audio_path: Path,
        num_speakers: Optional[int] = None,
    ) -> List[dict]:
        """
        Perform speaker diarization on audio.

        Args:
            audio_path: Path to audio file
            num_speakers: Expected number of speakers (auto-detect if None)

        Returns:
            List of diarization segments with speaker labels
        """
        # Load pipeline in thread pool (non-blocking)
        await self._load_pipeline()

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Diarizing: {audio_path}")

        # Run diarization in thread pool (non-blocking)
        loop = asyncio.get_event_loop()
        segments = await loop.run_in_executor(
            _diarization_executor,
            self._diarize_sync,
            str(audio_path),
            num_speakers,
        )

        # Get unique speakers
        speakers = set(seg["speaker"] for seg in segments)
        logger.info(f"Detected {len(speakers)} speakers: {speakers}")

        return segments

    async def merge_with_transcript(
        self,
        transcript: Transcript,
        diarization_segments: List[dict],
    ) -> DiarizedTranscript:
        """
        Merge transcript segments with speaker diarization.

        Args:
            transcript: Transcript with text segments
            diarization_segments: Diarization output

        Returns:
            DiarizedTranscript with speaker labels
        """
        diarized_segments: List[DiarizedSegment] = []

        for segment in transcript.segments:
            # Find the speaker for this segment based on overlap
            speaker = self._find_speaker(
                segment.start,
                segment.end,
                diarization_segments,
            )

            diarized_segments.append(
                DiarizedSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text,
                    speaker=speaker,
                )
            )

        # Count unique speakers
        speakers = set(seg.speaker for seg in diarized_segments)

        return DiarizedTranscript(
            language=transcript.language,
            num_speakers=len(speakers),
            segments=diarized_segments,
        )

    def _find_speaker(
        self,
        start: float,
        end: float,
        diarization_segments: List[dict],
    ) -> str:
        """Find the most likely speaker for a time range."""
        best_speaker = "SPEAKER_0"
        best_overlap = 0.0

        for d_seg in diarization_segments:
            # Calculate overlap
            overlap_start = max(start, d_seg["start"])
            overlap_end = min(end, d_seg["end"])
            overlap = max(0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = d_seg["speaker"]

        return best_speaker

    async def save_diarized_transcript(
        self,
        transcript: DiarizedTranscript,
        output_path: Path,
    ) -> None:
        """Save diarized transcript to JSON file."""
        import json

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(transcript.model_dump(), f, ensure_ascii=False, indent=2)

        logger.info(f"Diarized transcript saved to: {output_path}")
