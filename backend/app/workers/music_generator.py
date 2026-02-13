"""Music generation worker using Meta's MusicGen (audiocraft)."""

import asyncio
import random
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Optional

from loguru import logger

from app.config import settings
from app.models.music import AmbientMode, MusicModelSize, MusicTrackStatus
from app.services.ambient_library import AmbientLibrary
from app.services.music_manager import MusicManager

# Dedicated thread pool for GPU-bound model operations
_model_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="musicgen")

# CUDA errors that indicate GPU architecture incompatibility (auto-fallback to CPU)
_CUDA_FALLBACK_ERRORS = (
    "no kernel image is available",
    "CUDA error",
    "CUDA out of memory",
)

# Check if audiocraft is available
try:
    import audiocraft  # noqa: F401
    AUDIOCRAFT_AVAILABLE = True
except ImportError:
    AUDIOCRAFT_AVAILABLE = False
    logger.warning("audiocraft not installed - music generation disabled")


def _log_cuda_diagnostics():
    """Log GPU and CUDA info for debugging device compatibility issues."""
    try:
        import torch
        logger.info(f"PyTorch {torch.__version__}, CUDA compiled: {torch.version.cuda}")
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            cap = torch.cuda.get_device_capability(0)
            logger.info(f"GPU: {name}, compute capability: sm_{cap[0]}{cap[1]}")
        else:
            logger.warning("CUDA not available")
    except Exception as e:
        logger.warning(f"Could not read CUDA diagnostics: {e}")


class MusicGeneratorWorker:
    """Worker for AI music generation using MusicGen."""

    def __init__(self, music_manager: MusicManager, ambient_library: Optional[AmbientLibrary] = None):
        self.music_manager = music_manager
        self.ambient_library = ambient_library
        self.model = None
        self.current_model_size: Optional[MusicModelSize] = None
        self.device = getattr(settings, "music_device", "cuda")
        self._load_lock: Optional[asyncio.Lock] = None
        self._cuda_fallback_logged = False

    def _get_lock(self) -> asyncio.Lock:
        """Get or create the async lock (must be created in async context)."""
        if self._load_lock is None:
            self._load_lock = asyncio.Lock()
        return self._load_lock

    @property
    def is_available(self) -> bool:
        """Check if music generation is available."""
        return AUDIOCRAFT_AVAILABLE

    def _load_model_sync(self, model_size: MusicModelSize):
        """Synchronous model loading (runs in thread pool)."""
        from audiocraft.models import MusicGen

        model_id = model_size.hf_model_id
        logger.info(f"Loading MusicGen model: {model_id} on {self.device}")
        model = MusicGen.get_pretrained(model_id, device=self.device)

        # Enable FP16 on CUDA for better performance
        if self.device == "cuda":
            import torch
            if torch.cuda.is_available():
                model.lm = model.lm.half()
                logger.info("Enabled FP16 for MusicGen on CUDA")

        logger.info(f"MusicGen model loaded: {model_id}")
        return model

    async def _ensure_model_loaded(self, model_size: MusicModelSize):
        """Ensure model is loaded with the requested size."""
        if self.model is not None and self.current_model_size == model_size:
            return

        async with self._get_lock():
            # Double-check after acquiring lock
            if self.model is not None and self.current_model_size == model_size:
                return

            # Unload previous model if different size
            if self.model is not None and self.current_model_size != model_size:
                logger.info(f"Switching model from {self.current_model_size} to {model_size}")
                self.model = None

            logger.info(f"Loading MusicGen {model_size.value} model...")
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                _model_executor, self._load_model_sync, model_size
            )
            self.current_model_size = model_size

    def _generate_sync(self, prompt: str, duration: float) -> "torch.Tensor":
        """Synchronous music generation (runs in thread pool)."""
        import inspect
        import torch

        # Build generation params, handling parameter name changes across
        # audiocraft versions (cfg_coeff → cfg_scale / classifier_free_guidance)
        gen_params = {
            "duration": duration,
            "temperature": 1.0,
            "top_k": 250,
            "top_p": 0.0,
        }
        sig = inspect.signature(self.model.set_generation_params)
        for cfg_name in ("cfg_coeff", "cfg_scale", "classifier_free_guidance"):
            if cfg_name in sig.parameters:
                gen_params[cfg_name] = 3.0
                break

        self.model.set_generation_params(**gen_params)

        with torch.no_grad():
            wav = self.model.generate([prompt])

        return wav

    def _is_cuda_compat_error(self, error: Exception) -> bool:
        """Check if error is a CUDA compatibility issue that can be solved by CPU fallback."""
        msg = str(error)
        return any(pattern in msg for pattern in _CUDA_FALLBACK_ERRORS)

    def _fallback_to_cpu(self, reason: str):
        """Switch device to CPU after a CUDA failure."""
        if not self._cuda_fallback_logged:
            _log_cuda_diagnostics()
            self._cuda_fallback_logged = True
        logger.warning(f"Falling back to CPU for MusicGen: {reason}")
        self.device = "cpu"
        self.model = None
        self.current_model_size = None

    async def generate_music(
        self,
        track_id: str,
        prompt: str,
        duration: float,
        model_size: MusicModelSize,
        ambient_sounds: Optional[List[str]] = None,
        ambient_mode: AmbientMode = AmbientMode.MIX,
        ambient_volume: float = 0.3,
    ) -> None:
        """Generate music for a track. Updates track status via music_manager."""
        if not AUDIOCRAFT_AVAILABLE:
            self.music_manager.update_track(
                track_id,
                status=MusicTrackStatus.FAILED,
                error="audiocraft not installed",
            )
            return

        try:
            wav = await self._try_generate(track_id, prompt, duration, model_size)
        except Exception as e:
            # Auto-fallback: if CUDA fails, retry on CPU
            if self.device == "cuda" and self._is_cuda_compat_error(e):
                self._fallback_to_cpu(str(e))
                try:
                    wav = await self._try_generate(track_id, prompt, duration, model_size)
                except Exception as retry_err:
                    logger.error(f"Music generation failed on CPU fallback for {track_id}: {retry_err}")
                    self.music_manager.update_track(
                        track_id,
                        status=MusicTrackStatus.FAILED,
                        error=f"CPU fallback also failed: {retry_err}",
                    )
                    return
            else:
                logger.error(f"Music generation failed for {track_id}: {e}")
                self.music_manager.update_track(
                    track_id,
                    status=MusicTrackStatus.FAILED,
                    error=str(e),
                )
                return

        # Save audio file
        try:
            import torchaudio

            audio_dir = self.music_manager._track_dir(track_id)
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = audio_dir / "audio.wav"

            sample_rate = self.model.sample_rate
            # wav shape: (batch, channels, samples) -> take first batch item
            audio_data = wav[0].cpu()
            torchaudio.save(str(audio_path), audio_data, sample_rate)

            # Mix ambient sounds if requested
            if ambient_sounds and self.ambient_library:
                sound_paths = self.ambient_library.get_available_sounds(ambient_sounds)
                if sound_paths:
                    mixed_path = audio_dir / "mixed.wav"
                    await self._mix_ambient(
                        music_path=audio_path,
                        sound_paths=sound_paths,
                        ambient_mode=ambient_mode,
                        ambient_volume=ambient_volume,
                        duration=duration,
                        output_path=mixed_path,
                    )
                    # Replace audio.wav with mixed version
                    mixed_path.rename(audio_path)
                    logger.info(
                        f"Mixed {len(sound_paths)} ambient sound(s) into track {track_id} "
                        f"(mode={ambient_mode.value}, volume={ambient_volume})"
                    )

            file_size = audio_path.stat().st_size
            device_info = f" [device={self.device}]" if self.device == "cpu" else ""
            logger.info(
                f"Generated music track {track_id}: {duration}s, "
                f"{file_size / 1024:.1f}KB, sr={sample_rate}{device_info}"
            )

            self.music_manager.update_track(
                track_id,
                status=MusicTrackStatus.READY,
                file_path=str(audio_path),
                file_size_bytes=file_size,
            )
        except Exception as e:
            logger.error(f"Failed to save audio for {track_id}: {e}")
            self.music_manager.update_track(
                track_id,
                status=MusicTrackStatus.FAILED,
                error=str(e),
            )

    async def _mix_ambient(
        self,
        music_path: Path,
        sound_paths: List[Path],
        ambient_mode: AmbientMode,
        ambient_volume: float,
        duration: float,
        output_path: Path,
    ) -> None:
        """Mix ambient sounds into the AI-generated music using FFmpeg."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._mix_ambient_sync,
            music_path, sound_paths, ambient_mode, ambient_volume, duration, output_path,
        )

    def _mix_ambient_sync(
        self,
        music_path: Path,
        sound_paths: List[Path],
        ambient_mode: AmbientMode,
        ambient_volume: float,
        duration: float,
        output_path: Path,
    ) -> None:
        """Synchronous FFmpeg ambient mixing."""
        if ambient_mode == AmbientMode.SEQUENCE and len(sound_paths) > 1:
            self._mix_ambient_sequence(
                music_path, sound_paths, ambient_volume, duration, output_path,
            )
        else:
            self._mix_ambient_simultaneous(
                music_path, sound_paths, ambient_volume, duration, output_path,
            )

    def _mix_ambient_simultaneous(
        self,
        music_path: Path,
        sound_paths: List[Path],
        ambient_volume: float,
        duration: float,
        output_path: Path,
    ) -> None:
        """Mix mode: all ambient sounds play simultaneously, looped to match duration."""
        # Build FFmpeg command:
        # -i audio.wav -i rain.wav -i fireplace.wav
        # filter: loop each ambient, trim to duration, set volume, then amix all
        inputs = ["-i", str(music_path)]
        for sp in sound_paths:
            inputs += ["-i", str(sp)]

        n_ambient = len(sound_paths)
        n_total = 1 + n_ambient  # music + ambient inputs

        filter_parts = []
        mix_inputs = "[0:a]"

        for i, _ in enumerate(sound_paths):
            idx = i + 1
            # aloop: loop indefinitely, atrim: cut to target duration
            filter_parts.append(
                f"[{idx}:a]aloop=loop=-1:size=2e9,atrim=0:{duration},volume={ambient_volume}[a{idx}]"
            )
            mix_inputs += f"[a{idx}]"

        filter_parts.append(
            f"{mix_inputs}amix=inputs={n_total}:duration=first:normalize=0[out]"
        )
        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            str(output_path),
        ]

        logger.debug(f"FFmpeg ambient mix command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg ambient mix failed: {result.stderr[-500:]}")

    def _mix_ambient_sequence(
        self,
        music_path: Path,
        sound_paths: List[Path],
        ambient_volume: float,
        duration: float,
        output_path: Path,
    ) -> None:
        """Sequence mode: ambient sounds play in random order, concatenated, then mixed."""
        # Create a concat list file with randomized order, repeated enough times
        shuffled = list(sound_paths)
        random.shuffle(shuffled)

        # Repeat the shuffled list enough times to likely cover the duration
        # (we'll trim with atrim anyway)
        repeated = shuffled * max(1, int(duration / 10) + 1)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="ambient_concat_"
        ) as f:
            concat_file = f.name
            for sp in repeated:
                f.write(f"file '{sp}'\n")

        try:
            # Step 1: Concatenate ambient sounds
            concat_path = output_path.parent / "ambient_concat.wav"
            cmd_concat = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-t", str(duration),
                "-acodec", "pcm_s16le",
                str(concat_path),
            ]
            result = subprocess.run(cmd_concat, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg concat failed: {result.stderr[-500:]}")

            # Step 2: Mix concatenated ambient with music
            filter_complex = (
                f"[1:a]volume={ambient_volume}[amb];"
                f"[0:a][amb]amix=inputs=2:duration=first:normalize=0[out]"
            )
            cmd_mix = [
                "ffmpeg", "-y",
                "-i", str(music_path),
                "-i", str(concat_path),
                "-filter_complex", filter_complex,
                "-map", "[out]",
                str(output_path),
            ]
            result = subprocess.run(cmd_mix, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg sequence mix failed: {result.stderr[-500:]}")
        finally:
            # Clean up temp files
            Path(concat_file).unlink(missing_ok=True)
            concat_wav = output_path.parent / "ambient_concat.wav"
            concat_wav.unlink(missing_ok=True)

    async def _try_generate(
        self,
        track_id: str,
        prompt: str,
        duration: float,
        model_size: MusicModelSize,
    ):
        """Attempt to load model and generate audio. Raises on failure."""
        await self._ensure_model_loaded(model_size)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            _model_executor, self._generate_sync, prompt, duration
        )

    def get_status(self) -> dict:
        """Get worker status info."""
        status = {
            "available": AUDIOCRAFT_AVAILABLE,
            "device": self.device,
            "model_loaded": self.model is not None,
            "current_model_size": self.current_model_size.value if self.current_model_size else None,
            "cuda_fallback_active": self._cuda_fallback_logged,
        }
        if AUDIOCRAFT_AVAILABLE:
            try:
                import torch
                status["torch_version"] = torch.__version__
                status["torch_cuda_version"] = torch.version.cuda
                if torch.cuda.is_available():
                    status["gpu_name"] = torch.cuda.get_device_name(0)
                    cap = torch.cuda.get_device_capability(0)
                    status["gpu_compute_capability"] = f"sm_{cap[0]}{cap[1]}"
                    mem = torch.cuda.mem_get_info(0)
                    status["gpu_memory_free_gb"] = round(mem[0] / 1024**3, 2)
                    status["gpu_memory_total_gb"] = round(mem[1] / 1024**3, 2)
            except Exception:
                pass
        return status
