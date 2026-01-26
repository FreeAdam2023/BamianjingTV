"""Video download worker using yt-dlp."""

import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
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
        fetch_subtitles: bool = False,
        subtitle_langs: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Download video from URL.

        Args:
            url: Video URL (YouTube, etc.)
            output_dir: Directory to save files
            extract_audio: Whether to extract audio as WAV
            fetch_subtitles: Whether to download YouTube subtitles if available
            subtitle_langs: List of subtitle languages to try (default: ["en"])

        Returns:
            Dict with video_path, audio_path, subtitle_path, and metadata
        """
        output_dir = Path(output_dir)
        source_dir = output_dir / "source"
        source_dir.mkdir(parents=True, exist_ok=True)

        video_path = source_dir / "video.mp4"
        audio_path = source_dir / "audio.wav"
        subtitle_path = None

        if subtitle_langs is None:
            subtitle_langs = ["en"]

        # Get video info first
        info = await self._get_video_info(url)

        # Check duration
        duration = info.get("duration", 0)
        if duration > self.max_duration:
            raise ValueError(
                f"Video duration ({duration}s) exceeds maximum ({self.max_duration}s)"
            )

        # Check if this is a YouTube video and has subtitles
        is_youtube = self._is_youtube_url(url)
        has_subtitles = False

        if is_youtube and fetch_subtitles:
            # Check available subtitles
            available_subs = info.get("subtitles", {})
            auto_subs = info.get("automatic_captions", {})

            # Try to find requested language subtitles
            for lang in subtitle_langs:
                if lang in available_subs:
                    logger.info(f"Found manual subtitles for language: {lang}")
                    has_subtitles = True
                    break
                elif lang in auto_subs:
                    logger.info(f"Found auto-generated subtitles for language: {lang}")
                    has_subtitles = True
                    break

            if not has_subtitles:
                logger.info("No subtitles found for requested languages")

        # Check if video already exists (cache)
        if video_path.exists():
            logger.info(f"Video already exists, skipping download: {info.get('title', 'Unknown')}")
        else:
            # Download video
            logger.info(f"Downloading video: {info.get('title', 'Unknown')}")
            await self._download_video(url, video_path)

        # Download subtitles if requested and available
        if fetch_subtitles and has_subtitles:
            subtitle_path = await self._download_subtitles(
                url, source_dir, subtitle_langs
            )
            if subtitle_path:
                logger.info(f"Downloaded subtitles: {subtitle_path}")

        # Extract audio if requested (skip if we have subtitles and don't need audio for Whisper)
        if extract_audio:
            # Check if audio already exists (cache)
            if audio_path.exists():
                logger.info("Audio already exists, skipping extraction")
            else:
                logger.info("Extracting audio...")
                await self._extract_audio(video_path, audio_path)

        return {
            "video_path": str(video_path),
            "audio_path": str(audio_path) if extract_audio else None,
            "subtitle_path": str(subtitle_path) if subtitle_path else None,
            "has_youtube_subtitles": subtitle_path is not None,
            "title": info.get("title"),
            "duration": duration,
            "channel": info.get("channel") or info.get("uploader"),
            "description": info.get("description"),
        }

    def _is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube video."""
        url_lower = url.lower()
        return "youtube.com" in url_lower or "youtu.be" in url_lower

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

    async def _download_subtitles(
        self,
        url: str,
        output_dir: Path,
        langs: List[str],
    ) -> Optional[Path]:
        """
        Download subtitles from YouTube.

        Args:
            url: Video URL
            output_dir: Directory to save subtitle file
            langs: List of language codes to try (e.g., ["en", "en-US"])

        Returns:
            Path to subtitle file if successful, None otherwise
        """
        # Try manual subtitles first, then auto-generated
        for write_auto in [False, True]:
            subtitle_path = output_dir / "subtitle.en.vtt"

            cmd = [
                "yt-dlp",
                "--skip-download",
                "--sub-format", "vtt",
                "--sub-langs", ",".join(langs),
                "-o", str(output_dir / "subtitle"),
            ]

            if write_auto:
                cmd.append("--write-auto-subs")
            else:
                cmd.append("--write-subs")

            cmd.append(url)

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Check for downloaded subtitle file (yt-dlp adds language suffix)
            for lang in langs:
                possible_paths = [
                    output_dir / f"subtitle.{lang}.vtt",
                    output_dir / f"subtitle.{lang.split('-')[0]}.vtt",
                ]
                for path in possible_paths:
                    if path.exists():
                        # Rename to standard name
                        final_path = output_dir / "youtube_subtitle.vtt"
                        path.rename(final_path)
                        return final_path

        return None

    async def parse_youtube_subtitles(self, subtitle_path: Path) -> List[Dict[str, Any]]:
        """
        Parse VTT subtitle file into segments.

        Args:
            subtitle_path: Path to VTT file

        Returns:
            List of segments with start, end, and text
        """
        import re

        segments = []
        current_segment = None

        with open(subtitle_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Split into cues
        # VTT format: timestamp --> timestamp\ntext
        cue_pattern = re.compile(
            r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\s*\n(.*?)(?=\n\n|\Z)",
            re.DOTALL
        )

        for match in cue_pattern.finditer(content):
            start_str, end_str, text = match.groups()

            # Parse timestamps
            start = self._parse_vtt_timestamp(start_str)
            end = self._parse_vtt_timestamp(end_str)

            # Clean up text (remove HTML tags, extra whitespace)
            text = re.sub(r"<[^>]+>", "", text)  # Remove HTML tags
            text = re.sub(r"\s+", " ", text).strip()  # Normalize whitespace

            if text:
                segments.append({
                    "start": start,
                    "end": end,
                    "text": text,
                    "speaker": "SPEAKER_00",  # No speaker info from YouTube
                })

        # Merge consecutive segments with same text (YouTube often duplicates)
        merged = []
        for seg in segments:
            if merged and merged[-1]["text"] == seg["text"]:
                # Extend previous segment
                merged[-1]["end"] = seg["end"]
            else:
                merged.append(seg)

        logger.info(f"Parsed {len(merged)} segments from YouTube subtitles")
        return merged

    def _parse_vtt_timestamp(self, ts: str) -> float:
        """Parse VTT timestamp (HH:MM:SS.mmm) to seconds."""
        parts = ts.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds
