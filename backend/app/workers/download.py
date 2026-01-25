"""Video download worker using yt-dlp."""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger

from app.config import settings


class DownloadWorker:
    """Worker for downloading videos using yt-dlp."""

    def __init__(self):
        self.max_duration = settings.max_video_duration

    async def download(
        self,
        url: str,
        output_dir: Path,
        extract_audio: bool = True,
    ) -> Dict[str, Any]:
        """
        Download video from URL.

        Args:
            url: Video URL (YouTube, etc.)
            output_dir: Directory to save files
            extract_audio: Whether to extract audio as WAV

        Returns:
            Dict with video_path, audio_path, and metadata
        """
        output_dir = Path(output_dir)
        source_dir = output_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)

        video_path = source_dir / "video.mp4"
        audio_path = source_dir / "audio.wav"

        # Get video info first
        info = await self._get_video_info(url)

        # Check duration
        duration = info.get("duration", 0)
        if duration > self.max_duration:
            raise ValueError(
                f"Video duration ({duration}s) exceeds maximum ({self.max_duration}s)"
            )

        # Check if video already exists (cache)
        if video_path.exists():
            logger.info(f"视频已存在，跳过下载: {info.get('title', 'Unknown')}")
        else:
            # Download video
            logger.info(f"Downloading video: {info.get('title', 'Unknown')}")
            await self._download_video(url, video_path)

        # Extract audio if requested
        if extract_audio:
            # Check if audio already exists (cache)
            if audio_path.exists():
                logger.info("音频已存在，跳过提取")
            else:
                logger.info("Extracting audio...")
                await self._extract_audio(video_path, audio_path)

        return {
            "video_path": str(video_path),
            "audio_path": str(audio_path) if extract_audio else None,
            "title": info.get("title"),
            "duration": duration,
            "channel": info.get("channel") or info.get("uploader"),
            "description": info.get("description"),
        }

    async def _get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video metadata without downloading."""
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            url,
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )

        import json
        return json.loads(result.stdout)

    async def _download_video(self, url: str, output_path: Path) -> None:
        """Download video to specified path."""
        cmd = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", str(output_path),
            "--no-playlist",
            url,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {result.stderr}")

        if not output_path.exists():
            raise RuntimeError("Download completed but video file not found")

    async def _extract_audio(
        self, video_path: Path, audio_path: Path
    ) -> None:
        """Extract audio from video as WAV."""
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vn",  # No video
            "-acodec", "pcm_s16le",  # WAV format
            "-ar", "16000",  # 16kHz sample rate (good for Whisper)
            "-ac", "1",  # Mono
            "-y",  # Overwrite
            str(audio_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")

        if not audio_path.exists():
            raise RuntimeError("Audio extraction completed but file not found")
