"""Audio Mixer Worker - Mix dubbed audio with BGM and SFX."""

import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AudioMixerWorker:
    """
    Worker to mix dubbed vocals with background music and sound effects.

    Uses FFmpeg for audio processing and mixing.
    """

    def __init__(
        self,
        default_bgm_volume: float = 0.3,
        default_sfx_volume: float = 0.5,
        default_vocal_volume: float = 1.0,
        crossfade_duration: float = 0.1,
    ):
        """
        Initialize the audio mixer worker.

        Args:
            default_bgm_volume: Default volume for background music (0-1)
            default_sfx_volume: Default volume for sound effects (0-1)
            default_vocal_volume: Default volume for vocals (0-1)
            crossfade_duration: Duration for crossfades between segments (seconds)
        """
        self.default_bgm_volume = default_bgm_volume
        self.default_sfx_volume = default_sfx_volume
        self.default_vocal_volume = default_vocal_volume
        self.crossfade_duration = crossfade_duration

    async def mix_dubbed_audio(
        self,
        dubbed_segments: List[Dict],
        bgm_path: Path,
        sfx_path: Optional[Path],
        output_path: Path,
        total_duration: float,
        bgm_volume: Optional[float] = None,
        sfx_volume: Optional[float] = None,
        vocal_volume: Optional[float] = None,
    ) -> Path:
        """
        Mix dubbed segments with background music and sound effects.

        Args:
            dubbed_segments: List of segment dicts with start, end, dubbed_path
            bgm_path: Path to background music audio
            sfx_path: Path to sound effects audio (optional)
            output_path: Path for output mixed audio
            total_duration: Total duration of output (seconds)
            bgm_volume: Volume for BGM (0-1)
            sfx_volume: Volume for SFX (0-1)
            vocal_volume: Volume for vocals (0-1)

        Returns:
            Path to mixed audio file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        bgm_vol = bgm_volume if bgm_volume is not None else self.default_bgm_volume
        sfx_vol = sfx_volume if sfx_volume is not None else self.default_sfx_volume
        vocal_vol = vocal_volume if vocal_volume is not None else self.default_vocal_volume

        # First, create the dubbed vocal track by placing segments at correct times
        vocals_track = output_path.parent / "dubbed_vocals_track.wav"
        await self._create_vocals_track(dubbed_segments, vocals_track, total_duration)

        # Build FFmpeg filter for mixing
        inputs = []
        filter_parts = []

        # Input 0: Dubbed vocals
        inputs.extend(["-i", str(vocals_track)])
        filter_parts.append(f"[0:a]volume={vocal_vol}[vocals]")

        # Input 1: BGM
        inputs.extend(["-i", str(bgm_path)])
        filter_parts.append(f"[1:a]volume={bgm_vol}[bgm]")

        # Input 2: SFX (optional)
        if sfx_path and sfx_path.exists():
            inputs.extend(["-i", str(sfx_path)])
            filter_parts.append(f"[2:a]volume={sfx_vol}[sfx]")
            mix_inputs = "[vocals][bgm][sfx]"
            mix_count = 3
        else:
            mix_inputs = "[vocals][bgm]"
            mix_count = 2

        # Amix filter to combine all tracks
        filter_parts.append(f"{mix_inputs}amix=inputs={mix_count}:duration=longest[out]")

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", str(total_duration),
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            str(output_path)
        ]

        logger.info(f"Mixing audio tracks...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg mixing failed: {stderr.decode()}")

        # Cleanup temp file
        vocals_track.unlink(missing_ok=True)

        logger.info(f"Mixed audio saved to: {output_path}")
        return output_path

    async def _create_vocals_track(
        self,
        dubbed_segments: List[Dict],
        output_path: Path,
        total_duration: float,
    ) -> Path:
        """
        Create a single vocal track from dubbed segments.

        Places each dubbed segment at its correct time position,
        with silence between segments.

        Args:
            dubbed_segments: List of segment dicts with start, end, dubbed_path
            output_path: Path for output vocal track
            total_duration: Total duration in seconds

        Returns:
            Path to vocal track
        """
        # Filter segments with valid dubbed audio
        valid_segments = [
            s for s in dubbed_segments
            if s.get("dubbed_path") and Path(s["dubbed_path"]).exists()
        ]

        if not valid_segments:
            # Create silent track if no dubbed audio
            await self._create_silence(output_path, total_duration)
            return output_path

        # Build FFmpeg filter to place segments at correct times
        inputs = []
        filter_parts = []
        adelay_parts = []

        for i, seg in enumerate(valid_segments):
            inputs.extend(["-i", str(seg["dubbed_path"])])
            # Convert start time to milliseconds for adelay filter
            delay_ms = int(seg["start"] * 1000)
            adelay_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")

        # Build amix with all delayed segments
        if len(valid_segments) == 1:
            mix_filter = adelay_parts[0].replace(f"[a0]", "[out]")
            filter_complex = mix_filter
        else:
            filter_complex = ";".join(adelay_parts)
            mix_inputs = "".join(f"[a{i}]" for i in range(len(valid_segments)))
            filter_complex += f";{mix_inputs}amix=inputs={len(valid_segments)}:duration=longest[out]"

        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-t", str(total_duration),
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
            raise RuntimeError(f"Failed to create vocals track: {stderr.decode()}")

        logger.info(f"Created vocals track: {output_path}")
        return output_path

    async def _create_silence(self, output_path: Path, duration: float) -> Path:
        """Create a silent audio file."""
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
            "-acodec", "pcm_s16le",
            str(output_path)
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return output_path

    async def replace_video_audio(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> Path:
        """
        Replace video's audio track with new audio.

        Args:
            video_path: Path to original video
            audio_path: Path to new audio
            output_path: Path for output video

        Returns:
            Path to output video with replaced audio
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-c:v", "copy",  # Copy video stream
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            str(output_path)
        ]

        logger.info(f"Replacing video audio...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to replace audio: {stderr.decode()}")

        logger.info(f"Video with new audio saved to: {output_path}")
        return output_path

    async def adjust_audio_volume(
        self,
        audio_path: Path,
        output_path: Path,
        volume: float,
    ) -> Path:
        """
        Adjust audio volume.

        Args:
            audio_path: Path to input audio
            output_path: Path for output audio
            volume: Volume multiplier (0-2)

        Returns:
            Path to adjusted audio
        """
        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio_path),
            "-af", f"volume={volume}",
            str(output_path)
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to adjust volume: {stderr.decode()}")

        return output_path

    async def add_crossfade(
        self,
        audio1_path: Path,
        audio2_path: Path,
        output_path: Path,
        crossfade_duration: Optional[float] = None,
    ) -> Path:
        """
        Concatenate two audio files with crossfade.

        Args:
            audio1_path: Path to first audio
            audio2_path: Path to second audio
            output_path: Path for output audio
            crossfade_duration: Duration of crossfade (seconds)

        Returns:
            Path to concatenated audio
        """
        fade_dur = crossfade_duration or self.crossfade_duration

        cmd = [
            "ffmpeg", "-y",
            "-i", str(audio1_path),
            "-i", str(audio2_path),
            "-filter_complex",
            f"[0:a][1:a]acrossfade=d={fade_dur}:c1=tri:c2=tri[out]",
            "-map", "[out]",
            str(output_path)
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to add crossfade: {stderr.decode()}")

        return output_path
