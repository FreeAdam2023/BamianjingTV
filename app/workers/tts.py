"""Text-to-Speech worker using XTTS v2."""

import os
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger
import numpy as np

from app.config import settings
from app.models.transcript import TranslatedTranscript, TranslatedSegment


class TTSWorker:
    """Worker for Chinese TTS using XTTS v2."""

    def __init__(self):
        self.model = None
        self.model_name = settings.tts_model
        self.device = settings.tts_device
        self.speaker_embeddings: Dict[str, any] = {}

    def _load_model(self):
        """Lazy load the TTS model."""
        if self.model is None:
            from TTS.api import TTS

            logger.info(f"Loading TTS model: {self.model_name}")
            self.model = TTS(self.model_name).to(self.device)
            logger.info("TTS model loaded")

    async def extract_speaker_embedding(
        self,
        audio_path: Path,
        speaker_id: str,
    ) -> None:
        """
        Extract speaker embedding from reference audio.

        Args:
            audio_path: Path to reference audio
            speaker_id: Speaker identifier
        """
        self._load_model()

        # XTTS uses reference audio directly, we just store the path
        self.speaker_embeddings[speaker_id] = str(audio_path)
        logger.info(f"Stored reference audio for {speaker_id}: {audio_path}")

    async def extract_speaker_clips(
        self,
        audio_path: Path,
        diarization_segments: List[dict],
        output_dir: Path,
        clip_duration: float = 10.0,
    ) -> Dict[str, Path]:
        """
        Extract reference audio clips for each speaker.

        Args:
            audio_path: Path to full audio file
            diarization_segments: Diarization segments with speaker labels
            output_dir: Directory to save clips
            clip_duration: Target duration for reference clips

        Returns:
            Dict mapping speaker IDs to reference audio paths
        """
        import soundfile as sf

        audio_path = Path(audio_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Load audio
        audio, sr = sf.read(audio_path)

        # Group segments by speaker
        speaker_segments: Dict[str, List[dict]] = {}
        for seg in diarization_segments:
            speaker = seg["speaker"]
            if speaker not in speaker_segments:
                speaker_segments[speaker] = []
            speaker_segments[speaker].append(seg)

        # Extract best clip for each speaker
        speaker_clips: Dict[str, Path] = {}

        for speaker, segments in speaker_segments.items():
            # Sort by duration and pick longest segments
            segments.sort(key=lambda x: x["end"] - x["start"], reverse=True)

            # Collect audio until we have enough
            collected_audio = []
            total_duration = 0

            for seg in segments:
                if total_duration >= clip_duration:
                    break

                start_sample = int(seg["start"] * sr)
                end_sample = int(seg["end"] * sr)
                segment_audio = audio[start_sample:end_sample]

                collected_audio.append(segment_audio)
                total_duration += seg["end"] - seg["start"]

            if collected_audio:
                # Concatenate and save
                combined = np.concatenate(collected_audio)
                clip_path = output_dir / f"{speaker}_reference.wav"
                sf.write(clip_path, combined, sr)

                speaker_clips[speaker] = clip_path
                self.speaker_embeddings[speaker] = str(clip_path)
                logger.info(f"Extracted {total_duration:.1f}s reference for {speaker}")

        return speaker_clips

    async def synthesize_segment(
        self,
        text: str,
        speaker_id: str,
        output_path: Path,
    ) -> Path:
        """
        Synthesize speech for a single segment.

        Args:
            text: Chinese text to synthesize
            speaker_id: Speaker to use
            output_path: Path to save audio

        Returns:
            Path to generated audio
        """
        self._load_model()

        if speaker_id not in self.speaker_embeddings:
            raise ValueError(f"No reference audio for speaker: {speaker_id}")

        reference_audio = self.speaker_embeddings[speaker_id]
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate speech
        self.model.tts_to_file(
            text=text,
            file_path=str(output_path),
            speaker_wav=reference_audio,
            language="zh-cn",
        )

        return output_path

    async def synthesize_transcript(
        self,
        transcript: TranslatedTranscript,
        output_dir: Path,
    ) -> List[Dict]:
        """
        Synthesize all segments in a translated transcript.

        Args:
            transcript: Translated transcript
            output_dir: Directory to save audio files

        Returns:
            List of dicts with segment info and audio paths
        """
        self._load_model()

        output_dir = Path(output_dir)
        tts_dir = output_dir / "tts"
        tts_dir.mkdir(parents=True, exist_ok=True)

        results = []

        for i, segment in enumerate(transcript.segments):
            audio_path = tts_dir / f"segment_{i:04d}.wav"

            try:
                await self.synthesize_segment(
                    text=segment.translation,
                    speaker_id=segment.speaker,
                    output_path=audio_path,
                )

                results.append({
                    "index": i,
                    "start": segment.start,
                    "end": segment.end,
                    "speaker": segment.speaker,
                    "text": segment.translation,
                    "audio_path": str(audio_path),
                })

                if (i + 1) % 10 == 0:
                    logger.info(
                        f"Synthesized {i + 1}/{len(transcript.segments)} segments"
                    )

            except Exception as e:
                logger.error(f"Failed to synthesize segment {i}: {e}")
                results.append({
                    "index": i,
                    "start": segment.start,
                    "end": segment.end,
                    "speaker": segment.speaker,
                    "text": segment.translation,
                    "audio_path": None,
                    "error": str(e),
                })

        logger.info(f"Synthesized {len(results)} segments")
        return results
