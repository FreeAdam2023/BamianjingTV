"""Music generation worker using Meta's MusicGen (audiocraft)."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from loguru import logger

from app.config import settings
from app.models.music import MusicModelSize, MusicTrackStatus
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

    def __init__(self, music_manager: MusicManager):
        self.music_manager = music_manager
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
        import torch

        self.model.set_generation_params(
            duration=duration,
            temperature=1.0,
            top_k=250,
            top_p=0.0,
            cfg_coeff=3.0,
        )

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
