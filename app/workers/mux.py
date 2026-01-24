"""Video muxing worker using ffmpeg."""

import subprocess
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
import numpy as np

from app.config import settings


# ASS subtitle template with bilingual style (opaque box background)
ASS_HEADER = """[Script Info]
Title: MirrorFlow Bilingual Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: English,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&HC0000000,-1,0,0,0,100,100,0,0,3,0,0,8,20,20,60,1
Style: Chinese,Microsoft YaHei,52,&H0000FFFF,&H000000FF,&H00000000,&HC0000000,-1,0,0,0,100,100,0,0,3,0,0,2,20,20,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    centiseconds = int((secs - int(secs)) * 100)
    return f"{hours}:{minutes:02d}:{int(secs):02d}.{centiseconds:02d}"


class MuxWorker:
    """Worker for audio alignment and video muxing."""

    def __init__(self):
        self.use_nvenc = settings.ffmpeg_nvenc

    async def create_aligned_audio(
        self,
        tts_segments: List[Dict],
        total_duration: float,
        output_path: Path,
        sample_rate: int = 44100,
    ) -> Path:
        """
        Create aligned audio track from TTS segments.

        Args:
            tts_segments: List of TTS segment info with audio paths
            total_duration: Total duration of the video
            output_path: Path to save aligned audio
            sample_rate: Output sample rate

        Returns:
            Path to aligned audio file
        """
        import soundfile as sf

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create silence for the full duration
        total_samples = int(total_duration * sample_rate)
        aligned_audio = np.zeros(total_samples, dtype=np.float32)

        for seg in tts_segments:
            if seg.get("audio_path") is None:
                continue

            audio_path = Path(seg["audio_path"])
            if not audio_path.exists():
                logger.warning(f"Audio file not found: {audio_path}")
                continue

            # Load segment audio
            seg_audio, seg_sr = sf.read(audio_path)

            # Resample if needed
            if seg_sr != sample_rate:
                seg_audio = self._resample(seg_audio, seg_sr, sample_rate)

            # Calculate target position
            start_sample = int(seg["start"] * sample_rate)
            seg_samples = len(seg_audio)

            # Calculate target duration
            target_duration = seg["end"] - seg["start"]
            target_samples = int(target_duration * sample_rate)

            # Time-stretch if needed
            if abs(seg_samples - target_samples) > sample_rate * 0.1:  # >100ms difference
                seg_audio = self._time_stretch(
                    seg_audio, seg_samples, target_samples
                )
                seg_samples = len(seg_audio)

            # Mix into aligned audio
            end_sample = min(start_sample + seg_samples, total_samples)
            actual_samples = end_sample - start_sample

            if actual_samples > 0:
                aligned_audio[start_sample:end_sample] = seg_audio[:actual_samples]

        # Normalize audio
        max_val = np.max(np.abs(aligned_audio))
        if max_val > 0:
            aligned_audio = aligned_audio / max_val * 0.9

        # Save aligned audio
        sf.write(output_path, aligned_audio, sample_rate)
        logger.info(f"Created aligned audio: {output_path}")

        return output_path

    def _resample(
        self, audio: np.ndarray, src_sr: int, target_sr: int
    ) -> np.ndarray:
        """Resample audio to target sample rate."""
        from scipy import signal

        duration = len(audio) / src_sr
        target_samples = int(duration * target_sr)
        return signal.resample(audio, target_samples)

    def _time_stretch(
        self, audio: np.ndarray, current_samples: int, target_samples: int
    ) -> np.ndarray:
        """Simple time-stretch using resampling."""
        from scipy import signal

        return signal.resample(audio, target_samples)

    async def mux_video(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        keep_original_audio: bool = False,
        original_audio_volume: float = 0.1,
    ) -> Path:
        """
        Mux video with new audio track.

        Args:
            video_path: Path to source video
            audio_path: Path to new audio track
            output_path: Path for output video
            keep_original_audio: Whether to keep original audio as background
            original_audio_volume: Volume of original audio if kept

        Returns:
            Path to output video
        """
        video_path = Path(video_path)
        audio_path = Path(audio_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build ffmpeg command
        if keep_original_audio:
            # Mix original audio (lowered) with new audio
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-filter_complex",
                f"[0:a]volume={original_audio_volume}[orig];"
                f"[orig][1:a]amix=inputs=2:duration=first[aout]",
                "-map", "0:v",
                "-map", "[aout]",
            ]
        else:
            # Replace audio completely
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-i", str(audio_path),
                "-map", "0:v",
                "-map", "1:a",
            ]

        # Video encoding
        if self.use_nvenc:
            cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "medium"])

        # Audio encoding
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        # Output
        cmd.extend(["-y", str(output_path)])

        logger.info(f"Muxing video: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg mux failed: {result.stderr}")

        logger.info(f"Video muxed successfully: {output_path}")
        return output_path

    async def add_subtitles(
        self,
        video_path: Path,
        srt_path: Path,
        output_path: Path,
        burn_in: bool = False,
    ) -> Path:
        """
        Add subtitles to video.

        Args:
            video_path: Path to video
            srt_path: Path to SRT subtitle file
            output_path: Path for output video
            burn_in: Whether to burn subtitles into video

        Returns:
            Path to output video
        """
        video_path = Path(video_path)
        srt_path = Path(srt_path)
        output_path = Path(output_path)

        if burn_in:
            # Burn subtitles into video
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-vf", f"subtitles={srt_path}",
            ]
            if self.use_nvenc:
                cmd.extend(["-c:v", "h264_nvenc"])
            else:
                cmd.extend(["-c:v", "libx264"])
        else:
            # Add as soft subtitles
            cmd = [
                "ffmpeg",
                "-i", str(video_path),
                "-i", str(srt_path),
                "-c:v", "copy",
                "-c:s", "mov_text",
                "-metadata:s:s:0", "language=zho",
            ]

        cmd.extend(["-c:a", "copy", "-y", str(output_path)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg subtitle failed: {result.stderr}")

        return output_path

    async def generate_bilingual_ass(
        self,
        segments: List[Dict],
        output_path: Path,
        use_traditional: bool = True,
    ) -> Path:
        """
        Generate ASS subtitle file with bilingual subtitles.

        Args:
            segments: List of segments with 'text' (English) and 'translation' (Chinese)
            output_path: Path to save ASS file
            use_traditional: Use Traditional Chinese (default True)

        Returns:
            Path to ASS file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert Simplified to Traditional if needed
        if use_traditional:
            try:
                import opencc
                converter = opencc.OpenCC('s2t')  # Simplified to Traditional
            except ImportError:
                logger.warning("opencc not installed, using Simplified Chinese")
                converter = None
        else:
            converter = None

        lines = [ASS_HEADER]

        for seg in segments:
            start = _seconds_to_ass_time(seg["start"])
            end = _seconds_to_ass_time(seg["end"])

            # English subtitle (top, white)
            english_text = seg.get("text", "").replace("\n", "\\N")
            if english_text:
                lines.append(f"Dialogue: 0,{start},{end},English,,0,0,0,,{english_text}")

            # Chinese subtitle (bottom, yellow)
            chinese_text = seg.get("translation", "").replace("\n", "\\N")
            if chinese_text:
                if converter:
                    chinese_text = converter.convert(chinese_text)
                lines.append(f"Dialogue: 0,{start},{end},Chinese,,0,0,0,,{chinese_text}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated bilingual ASS subtitle: {output_path}")
        return output_path

    async def burn_bilingual_subtitles(
        self,
        video_path: Path,
        segments: List[Dict],
        output_path: Path,
        use_traditional: bool = True,
    ) -> Path:
        """
        Burn bilingual subtitles into video.

        Style:
        - English: Top area, white text, black outline
        - Chinese: Bottom area, yellow text (繁体), black outline

        Args:
            video_path: Input video path
            segments: Transcript segments with 'text' and 'translation'
            output_path: Output video path
            use_traditional: Use Traditional Chinese

        Returns:
            Path to output video with burned subtitles
        """
        video_path = Path(video_path)
        output_path = Path(output_path)

        # Generate ASS file
        ass_path = output_path.parent / "subtitles_bilingual.ass"
        await self.generate_bilingual_ass(segments, ass_path, use_traditional)

        # Escape special characters in path for ffmpeg filter
        ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")

        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"ass={ass_path_escaped}",
        ]

        if self.use_nvenc:
            cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "23"])

        cmd.extend(["-c:a", "copy", "-y", str(output_path)])

        logger.info(f"Burning bilingual subtitles: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg subtitle burn failed: {result.stderr}")

        logger.info(f"Bilingual subtitles burned successfully: {output_path}")
        return output_path

    async def mux_video_with_subtitles(
        self,
        video_path: Path,
        audio_path: Path,
        segments: List[Dict],
        output_path: Path,
        keep_original_audio: bool = False,
        original_audio_volume: float = 0.1,
        burn_subtitles: bool = True,
        use_traditional: bool = True,
    ) -> Path:
        """
        Complete mux: replace audio + burn bilingual subtitles.

        Args:
            video_path: Source video
            audio_path: New audio (TTS)
            segments: Transcript segments for subtitles
            output_path: Final output path
            keep_original_audio: Mix original audio
            original_audio_volume: Original audio volume
            burn_subtitles: Whether to burn subtitles
            use_traditional: Use Traditional Chinese

        Returns:
            Path to final video
        """
        output_path = Path(output_path)
        temp_dir = output_path.parent

        # Step 1: Mux video with new audio
        temp_muxed = temp_dir / "temp_muxed.mp4"
        await self.mux_video(
            video_path=video_path,
            audio_path=audio_path,
            output_path=temp_muxed,
            keep_original_audio=keep_original_audio,
            original_audio_volume=original_audio_volume,
        )

        if not burn_subtitles:
            # Just rename temp file to output
            temp_muxed.rename(output_path)
            return output_path

        # Step 2: Burn bilingual subtitles
        await self.burn_bilingual_subtitles(
            video_path=temp_muxed,
            segments=segments,
            output_path=output_path,
            use_traditional=use_traditional,
        )

        # Cleanup temp file
        if temp_muxed.exists():
            temp_muxed.unlink()

        return output_path
