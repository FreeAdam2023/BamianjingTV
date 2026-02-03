"""Voice Clone Worker - Clone voices and synthesize speech using XTTS v2."""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Check if TTS is available
try:
    import torch
    import torchaudio
    from TTS.api import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    logger.warning("TTS (Coqui) not installed. Voice cloning will not be available.")


class VoiceCloneWorker:
    """
    Worker to clone voices and synthesize speech using XTTS v2.

    XTTS v2 can clone any voice from a short audio sample and
    generate speech in that voice for any text.
    """

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        device: Optional[str] = None,
    ):
        """
        Initialize the voice clone worker.

        Args:
            model_name: TTS model to use
            device: Device to run on (cuda, cpu, or None for auto)
        """
        self.model_name = model_name
        self.tts = None

        if device is None:
            self.device = "cuda" if TTS_AVAILABLE and torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Cache for speaker embeddings (speaker_id -> embedding)
        self._speaker_cache: Dict[str, object] = {}

    def _load_model(self):
        """Load the TTS model lazily."""
        if self.tts is not None:
            return

        if not TTS_AVAILABLE:
            raise RuntimeError("TTS (Coqui) is not installed. Run: pip install TTS")

        logger.info(f"Loading TTS model: {self.model_name} on {self.device}")
        self.tts = TTS(self.model_name).to(self.device)
        logger.info("TTS model loaded successfully")

    async def extract_speaker_sample(
        self,
        audio_path: Path,
        segments: List[Dict],
        speaker_id: str,
        output_dir: Path,
        min_duration: float = 6.0,
        max_duration: float = 30.0,
    ) -> Optional[Path]:
        """
        Extract a clean audio sample for a specific speaker.

        Args:
            audio_path: Path to full audio file
            segments: List of segment dicts with speaker, start, end
            speaker_id: Speaker ID to extract
            output_dir: Directory to save sample
            min_duration: Minimum sample duration (seconds)
            max_duration: Maximum sample duration (seconds)

        Returns:
            Path to speaker sample audio, or None if not enough audio
        """
        import torchaudio

        output_dir.mkdir(parents=True, exist_ok=True)
        sample_path = output_dir / f"speaker_{speaker_id}_sample.wav"

        # Filter segments for this speaker
        speaker_segments = [
            s for s in segments
            if s.get("speaker") == speaker_id
        ]

        if not speaker_segments:
            logger.warning(f"No segments found for speaker {speaker_id}")
            return None

        # Sort by duration and quality (prefer longer, cleaner segments)
        speaker_segments.sort(key=lambda s: s["end"] - s["start"], reverse=True)

        # Load original audio
        waveform, sample_rate = torchaudio.load(audio_path)

        # Collect segments until we have enough duration
        collected_audio = []
        total_duration = 0.0

        for seg in speaker_segments:
            start_sample = int(seg["start"] * sample_rate)
            end_sample = int(seg["end"] * sample_rate)

            segment_audio = waveform[:, start_sample:end_sample]
            segment_duration = (end_sample - start_sample) / sample_rate

            collected_audio.append(segment_audio)
            total_duration += segment_duration

            if total_duration >= max_duration:
                break

        if total_duration < min_duration:
            logger.warning(
                f"Not enough audio for speaker {speaker_id}: "
                f"{total_duration:.1f}s < {min_duration}s"
            )
            # Still try with what we have if it's at least 3 seconds
            if total_duration < 3.0:
                return None

        # Concatenate collected segments
        if not collected_audio:
            return None

        combined = torch.cat(collected_audio, dim=1)

        # Ensure mono for speaker embedding
        if combined.shape[0] > 1:
            combined = combined.mean(dim=0, keepdim=True)

        # Save sample
        torchaudio.save(str(sample_path), combined, sample_rate)
        logger.info(f"Extracted speaker sample: {sample_path} ({total_duration:.1f}s)")

        return sample_path

    async def synthesize(
        self,
        text: str,
        speaker_sample_path: Path,
        output_path: Path,
        language: str = "zh-cn",
        speed: float = 1.0,
    ) -> Path:
        """
        Synthesize speech in a cloned voice.

        Args:
            text: Text to synthesize
            speaker_sample_path: Path to speaker's voice sample
            output_path: Path for output audio
            language: Target language code
            speed: Speech speed multiplier (0.5-2.0)

        Returns:
            Path to synthesized audio
        """
        self._load_model()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Synthesizing: '{text[:50]}...' in voice from {speaker_sample_path}")

        def _synthesize():
            self.tts.tts_to_file(
                text=text,
                speaker_wav=str(speaker_sample_path),
                language=language,
                file_path=str(output_path),
                speed=speed,
            )

        # Run in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _synthesize)

        logger.info(f"Synthesized audio saved to: {output_path}")
        return output_path

    async def synthesize_segment(
        self,
        text: str,
        speaker_sample_path: Path,
        target_duration: float,
        output_path: Path,
        language: str = "zh-cn",
        max_speed: float = 1.5,
        min_speed: float = 0.8,
    ) -> Tuple[Path, float]:
        """
        Synthesize speech and adjust speed to match target duration.

        Args:
            text: Text to synthesize
            speaker_sample_path: Path to speaker's voice sample
            target_duration: Target duration in seconds
            output_path: Path for output audio
            language: Target language code
            max_speed: Maximum speech speed
            min_speed: Minimum speech speed

        Returns:
            Tuple of (output_path, actual_duration)
        """
        import torchaudio

        # First, synthesize at normal speed to measure duration
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            temp_path = Path(tmp.name)

        await self.synthesize(text, speaker_sample_path, temp_path, language, speed=1.0)

        # Measure duration
        waveform, sample_rate = torchaudio.load(temp_path)
        original_duration = waveform.shape[1] / sample_rate

        # Calculate required speed adjustment
        if target_duration > 0:
            speed_ratio = original_duration / target_duration
            speed = max(min_speed, min(max_speed, speed_ratio))
        else:
            speed = 1.0

        # If speed is close to 1.0, use the original
        if 0.95 <= speed <= 1.05:
            temp_path.rename(output_path)
            return output_path, original_duration

        # Re-synthesize with adjusted speed
        await self.synthesize(text, speaker_sample_path, output_path, language, speed=speed)
        temp_path.unlink(missing_ok=True)

        # Get actual duration
        waveform, sample_rate = torchaudio.load(output_path)
        actual_duration = waveform.shape[1] / sample_rate

        logger.info(
            f"Adjusted duration: {original_duration:.2f}s -> {actual_duration:.2f}s "
            f"(target: {target_duration:.2f}s, speed: {speed:.2f})"
        )

        return output_path, actual_duration

    async def dub_segments(
        self,
        segments: List[Dict],
        speaker_samples: Dict[str, Path],
        output_dir: Path,
        language: str = "zh-cn",
    ) -> List[Dict]:
        """
        Dub multiple segments with cloned voices.

        Args:
            segments: List of segment dicts with id, text, speaker, start, end
            speaker_samples: Map of speaker_id -> sample audio path
            output_dir: Directory to save dubbed audio
            language: Target language code

        Returns:
            List of segment dicts with added 'dubbed_path' and 'dubbed_duration'
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for seg in segments:
            speaker_id = seg.get("speaker", "unknown")
            sample_path = speaker_samples.get(speaker_id)

            if not sample_path or not sample_path.exists():
                logger.warning(f"No sample for speaker {speaker_id}, skipping segment {seg['id']}")
                results.append({**seg, "dubbed_path": None, "dubbed_duration": None})
                continue

            text = seg.get("zh") or seg.get("text", "")
            if not text.strip():
                logger.warning(f"Empty text for segment {seg['id']}, skipping")
                results.append({**seg, "dubbed_path": None, "dubbed_duration": None})
                continue

            target_duration = seg["end"] - seg["start"]
            output_path = output_dir / f"segment_{seg['id']}_dubbed.wav"

            try:
                dubbed_path, dubbed_duration = await self.synthesize_segment(
                    text=text,
                    speaker_sample_path=sample_path,
                    target_duration=target_duration,
                    output_path=output_path,
                    language=language,
                )
                results.append({
                    **seg,
                    "dubbed_path": str(dubbed_path),
                    "dubbed_duration": dubbed_duration,
                })
            except Exception as e:
                logger.error(f"Failed to dub segment {seg['id']}: {e}")
                results.append({**seg, "dubbed_path": None, "dubbed_duration": None, "error": str(e)})

        return results

    def get_device_info(self) -> dict:
        """Get information about the compute device."""
        info = {
            "tts_available": TTS_AVAILABLE,
            "device": self.device,
            "model_name": self.model_name,
        }

        if TTS_AVAILABLE:
            import torch
            info["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                info["cuda_device"] = torch.cuda.get_device_name(0)
                info["cuda_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / 1e9

        return info
