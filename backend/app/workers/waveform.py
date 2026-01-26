"""Waveform generation worker for timeline visualization."""

import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


class WaveformWorker:
    """Worker for generating audio waveform peak data."""

    def __init__(self, samples_per_second: int = 1000):
        """
        Initialize waveform worker.

        Args:
            samples_per_second: Number of peak samples per second of audio.
                Higher values = more detail but larger files.
                1000 = 1ms resolution (good default)
                500 = 2ms resolution (smaller files)
                100 = 10ms resolution (minimal detail)
        """
        self.samples_per_second = samples_per_second

    async def generate_peaks(
        self,
        audio_path: Path,
        output_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Generate waveform peak data from an audio file.

        Args:
            audio_path: Path to the audio file (WAV, MP3, etc.)
            output_path: Optional path to save the peaks JSON file.
                If not provided, peaks are returned but not saved.

        Returns:
            Dict with peaks, sample_rate, and duration
        """
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(f"Generating waveform peaks for: {audio_path}")

        # Read audio file using scipy (supports more formats) or soundfile
        try:
            # Try scipy first (handles more formats)
            from scipy.io import wavfile
            sample_rate, audio_data = wavfile.read(str(audio_path))

            # Convert to float and normalize
            if audio_data.dtype == np.int16:
                audio_data = audio_data.astype(np.float32) / 32768.0
            elif audio_data.dtype == np.int32:
                audio_data = audio_data.astype(np.float32) / 2147483648.0
            elif audio_data.dtype == np.float64:
                audio_data = audio_data.astype(np.float32)

        except Exception as e:
            logger.warning(f"scipy failed, trying soundfile: {e}")
            try:
                import soundfile as sf
                audio_data, sample_rate = sf.read(str(audio_path))
                audio_data = audio_data.astype(np.float32)
            except ImportError:
                raise RuntimeError(
                    "Neither scipy nor soundfile could read the audio. "
                    "Install soundfile: pip install soundfile"
                )

        # Convert stereo to mono if needed
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)

        # Calculate duration
        duration = len(audio_data) / sample_rate
        logger.info(f"Audio duration: {duration:.2f}s, sample rate: {sample_rate}Hz")

        # Calculate number of peak samples
        total_peaks = int(duration * self.samples_per_second)
        if total_peaks < 1:
            total_peaks = 1

        samples_per_peak = len(audio_data) / total_peaks

        # Generate peaks
        peaks = []
        for i in range(total_peaks):
            start_idx = int(i * samples_per_peak)
            end_idx = int((i + 1) * samples_per_peak)
            end_idx = min(end_idx, len(audio_data))

            if start_idx >= end_idx:
                peaks.append(0.0)
                continue

            window = audio_data[start_idx:end_idx]
            # Use max absolute value for peak
            peak_value = float(np.max(np.abs(window)))
            peaks.append(peak_value)

        # Normalize peaks to 0-1 range
        max_peak = max(peaks) if peaks else 1.0
        if max_peak > 0:
            peaks = [p / max_peak for p in peaks]

        result = {
            "peaks": peaks,
            "sample_rate": self.samples_per_second,
            "duration": duration,
            "original_sample_rate": sample_rate,
            "total_samples": len(peaks),
        }

        # Save to file if output path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(result, f)

            logger.info(f"Saved waveform peaks to: {output_path}")

            # Add file size info
            file_size_kb = output_path.stat().st_size / 1024
            result["file_size_kb"] = round(file_size_kb, 2)
            logger.info(f"Waveform file size: {file_size_kb:.2f} KB")

        return result

    async def load_peaks(self, peaks_path: Path) -> Optional[Dict[str, Any]]:
        """
        Load waveform peaks from a JSON file.

        Args:
            peaks_path: Path to the peaks JSON file

        Returns:
            Dict with peaks data, or None if file doesn't exist
        """
        peaks_path = Path(peaks_path)

        if not peaks_path.exists():
            return None

        try:
            with open(peaks_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load peaks: {e}")
            return None

    async def generate_for_job(
        self,
        job_dir: Path,
        track_type: str = "original",
    ) -> Dict[str, Any]:
        """
        Generate waveform peaks for a job's audio file.

        Args:
            job_dir: Path to the job directory
            track_type: Type of audio track ("original", "dubbing", "bgm")

        Returns:
            Dict with peaks data and file paths
        """
        job_dir = Path(job_dir)

        # Determine audio file path based on track type
        if track_type == "original":
            audio_path = job_dir / "source" / "audio.wav"
        elif track_type == "dubbing":
            audio_path = job_dir / "tts" / "dubbing.wav"
        elif track_type == "bgm":
            audio_path = job_dir / "source" / "bgm.wav"
        else:
            raise ValueError(f"Unknown track type: {track_type}")

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Create waveforms directory
        waveforms_dir = job_dir / "waveforms"
        waveforms_dir.mkdir(parents=True, exist_ok=True)

        output_path = waveforms_dir / f"{track_type}.json"

        # Check cache
        if output_path.exists():
            logger.info(f"Loading cached waveform: {output_path}")
            cached = await self.load_peaks(output_path)
            if cached:
                cached["cached"] = True
                return cached

        # Generate new peaks
        result = await self.generate_peaks(audio_path, output_path)
        result["cached"] = False
        result["track_type"] = track_type
        result["audio_path"] = str(audio_path)
        result["peaks_path"] = str(output_path)

        return result
