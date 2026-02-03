"""Audio Separation Worker - Separate vocals, BGM, and SFX using Demucs."""

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Check if demucs is available
try:
    import torch
    import torchaudio
    DEMUCS_AVAILABLE = True
except ImportError:
    DEMUCS_AVAILABLE = False
    logger.warning("Demucs dependencies not installed. Audio separation will use FFmpeg fallback.")


class AudioSeparationWorker:
    """
    Worker to separate audio into vocals, background music, and sound effects.

    Uses Demucs (htdemucs) model for high-quality separation.
    Falls back to basic FFmpeg filtering if Demucs is not available.
    """

    def __init__(self, model_name: str = "htdemucs", device: Optional[str] = None):
        """
        Initialize the audio separation worker.

        Args:
            model_name: Demucs model to use (htdemucs, htdemucs_ft, mdx_extra)
            device: Device to run on (cuda, cpu, or None for auto)
        """
        self.model_name = model_name
        self.model = None

        if device is None:
            self.device = "cuda" if DEMUCS_AVAILABLE and torch.cuda.is_available() else "cpu"
        else:
            self.device = device

    def _load_model(self):
        """Load the Demucs model lazily."""
        if self.model is not None:
            return

        if not DEMUCS_AVAILABLE:
            raise RuntimeError("Demucs is not installed. Run: pip install demucs")

        try:
            from demucs.pretrained import get_model
            from demucs.apply import apply_model

            logger.info(f"Loading Demucs model: {self.model_name} on {self.device}")
            self.model = get_model(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info("Demucs model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Demucs model: {e}")
            raise

    async def separate(
        self,
        audio_path: Path,
        output_dir: Path,
        shifts: int = 1,
        overlap: float = 0.25,
    ) -> Tuple[Path, Path, Path]:
        """
        Separate audio into vocals, drums, bass, and other.

        Args:
            audio_path: Path to input audio file
            output_dir: Directory to save separated audio
            shifts: Number of random shifts for better quality (1-10)
            overlap: Overlap ratio for segments (0-0.5)

        Returns:
            Tuple of (vocals_path, bgm_path, sfx_path)
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        vocals_path = output_dir / "vocals.wav"
        bgm_path = output_dir / "bgm.wav"
        sfx_path = output_dir / "sfx.wav"

        if DEMUCS_AVAILABLE:
            await self._separate_with_demucs(
                audio_path, output_dir, vocals_path, bgm_path, sfx_path, shifts, overlap
            )
        else:
            await self._separate_with_ffmpeg(
                audio_path, vocals_path, bgm_path, sfx_path
            )

        return vocals_path, bgm_path, sfx_path

    async def _separate_with_demucs(
        self,
        audio_path: Path,
        output_dir: Path,
        vocals_path: Path,
        bgm_path: Path,
        sfx_path: Path,
        shifts: int,
        overlap: float,
    ):
        """Separate audio using Demucs model."""
        self._load_model()

        from demucs.apply import apply_model
        import torch
        import torchaudio

        # Load audio
        logger.info(f"Loading audio: {audio_path}")
        waveform, sample_rate = torchaudio.load(audio_path)

        # Resample to model's sample rate if needed (Demucs uses 44100)
        if sample_rate != 44100:
            logger.info(f"Resampling from {sample_rate} to 44100")
            resampler = torchaudio.transforms.Resample(sample_rate, 44100)
            waveform = resampler(waveform)
            sample_rate = 44100

        # Ensure stereo
        if waveform.shape[0] == 1:
            waveform = waveform.repeat(2, 1)
        elif waveform.shape[0] > 2:
            waveform = waveform[:2]

        # Add batch dimension
        waveform = waveform.unsqueeze(0).to(self.device)

        # Apply model
        logger.info("Separating audio with Demucs...")

        def _apply():
            with torch.no_grad():
                return apply_model(
                    self.model,
                    waveform,
                    shifts=shifts,
                    overlap=overlap,
                    progress=True,
                )

        # Run in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        sources = await loop.run_in_executor(None, _apply)

        # Sources shape: [batch, sources, channels, samples]
        # htdemucs sources: drums, bass, other, vocals
        sources = sources.squeeze(0).cpu()

        # Get source indices (htdemucs order: drums, bass, other, vocals)
        vocals = sources[3]  # vocals
        drums = sources[0]   # drums (part of SFX)
        bass = sources[1]    # bass (part of BGM)
        other = sources[2]   # other (part of BGM)

        # Combine for BGM (bass + other) and SFX (drums)
        bgm = bass + other
        sfx = drums

        # Save separated audio
        logger.info("Saving separated audio...")
        torchaudio.save(str(vocals_path), vocals, sample_rate)
        torchaudio.save(str(bgm_path), bgm, sample_rate)
        torchaudio.save(str(sfx_path), sfx, sample_rate)

        logger.info(f"Audio separation complete: {vocals_path}, {bgm_path}, {sfx_path}")

    async def _separate_with_ffmpeg(
        self,
        audio_path: Path,
        vocals_path: Path,
        bgm_path: Path,
        sfx_path: Path,
    ):
        """
        Basic audio separation using FFmpeg filters.

        This is a simple fallback that uses:
        - Center channel extraction for vocals (mono from stereo center)
        - Side channel extraction for BGM
        - High-pass filter for SFX approximation

        Note: Quality is much lower than Demucs.
        """
        logger.warning("Using FFmpeg fallback for audio separation (lower quality)")

        # Extract vocals (center channel - vocals are usually centered)
        vocals_cmd = [
            "ffmpeg", "-y", "-i", str(audio_path),
            "-af", "pan=stereo|c0=0.5*c0+0.5*c1|c1=0.5*c0+0.5*c1",
            str(vocals_path)
        ]

        # Extract BGM (side channels)
        bgm_cmd = [
            "ffmpeg", "-y", "-i", str(audio_path),
            "-af", "pan=stereo|c0=c0-c1|c1=c1-c0,volume=2",
            str(bgm_path)
        ]

        # Copy original as SFX placeholder (in real Demucs, drums would be extracted)
        sfx_cmd = [
            "ffmpeg", "-y", "-i", str(audio_path),
            "-af", "highpass=f=8000,volume=0.3",
            str(sfx_path)
        ]

        for cmd in [vocals_cmd, bgm_cmd, sfx_cmd]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                logger.error(f"FFmpeg error: {stderr.decode()}")

        logger.info("FFmpeg audio separation complete (fallback mode)")

    async def extract_audio(self, video_path: Path, output_path: Path) -> Path:
        """
        Extract audio from video file.

        Args:
            video_path: Path to video file
            output_path: Path for output audio file

        Returns:
            Path to extracted audio
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-vn",  # No video
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path)
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to extract audio: {stderr.decode()}")

        logger.info(f"Extracted audio to: {output_path}")
        return output_path

    def get_device_info(self) -> dict:
        """Get information about the compute device."""
        info = {
            "demucs_available": DEMUCS_AVAILABLE,
            "device": self.device,
            "model_name": self.model_name,
        }

        if DEMUCS_AVAILABLE:
            import torch
            info["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                info["cuda_device"] = torch.cuda.get_device_name(0)
                info["cuda_memory_gb"] = torch.cuda.get_device_properties(0).total_memory / 1e9

        return info
