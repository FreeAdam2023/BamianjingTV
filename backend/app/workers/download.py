"""Video download worker using yt-dlp."""

import html
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
        prefer_auto_subs: bool = False,
        subtitle_langs: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Download video from URL or use local file.

        Args:
            url: Video URL (YouTube, etc.) or file:// path for uploaded files
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

        audio_path = source_dir / "audio.wav"
        subtitle_path = None

        if subtitle_langs is None:
            subtitle_langs = ["en"]

        # Handle local file uploads (file:// URLs)
        if url.startswith("file://"):
            return await self._handle_local_file(
                url, source_dir, audio_path, extract_audio
            )

        # Standard video path for downloads
        video_path = source_dir / "video.mp4"

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

            # Check for manual (human-uploaded) subtitles first
            # Use prefix matching to handle variants like en-US, en-GB, etc.
            for lang in subtitle_langs:
                matched = [k for k in available_subs if k == lang or k.startswith(f"{lang}-")]
                if matched:
                    logger.info(f"Found manual subtitles for language: {lang} (matched: {matched})")
                    has_subtitles = True
                    break

            # If no manual subs found and auto subs requested, accept auto-generated
            if not has_subtitles and prefer_auto_subs:
                auto_matched = [
                    k for k in auto_subs
                    for lang in subtitle_langs
                    if k == lang or k.startswith(f"{lang}-")
                ]
                if auto_matched:
                    logger.info(f"Using auto-generated subtitles ({auto_matched}) as requested")
                    has_subtitles = True
                else:
                    logger.info("No subtitles found for requested languages")
            elif not has_subtitles:
                auto_matched = [
                    k for k in auto_subs
                    for lang in subtitle_langs
                    if k == lang or k.startswith(f"{lang}-")
                ]
                if auto_matched:
                    logger.info(f"Only auto-generated subtitles found ({auto_matched}), preferring Whisper")
                else:
                    logger.info("No subtitles found for requested languages")

        # Check if video already exists (cache)
        if video_path.exists():
            logger.info(f"Video already exists, skipping download: {info.get('title', 'Unknown')}")
        else:
            # Download video
            logger.info(f"Downloading video: {info.get('title', 'Unknown')}")
            await self._download_video(url, video_path)

        # Download subtitles if requested and available
        zh_subtitle_path = None
        if fetch_subtitles and has_subtitles:
            subtitle_path = await self._download_subtitles(
                url, source_dir, subtitle_langs, prefer_auto=prefer_auto_subs
            )
            if subtitle_path:
                logger.info(f"Downloaded subtitles: {subtitle_path}")

            # Try downloading Chinese subtitles for bilingual mode
            zh_subtitle_path = await self._download_zh_subtitles(
                url, source_dir, info, prefer_auto=prefer_auto_subs
            )
            if zh_subtitle_path:
                logger.info(f"Downloaded Chinese subtitles: {zh_subtitle_path}")

        # Extract audio if requested (skip if we have subtitles and don't need audio for Whisper)
        if extract_audio:
            # Check if audio already exists (cache)
            if audio_path.exists():
                logger.info("Audio already exists, skipping extraction")
            else:
                logger.info("Extracting audio...")
                await self._extract_audio(video_path, audio_path)

        has_bilingual = subtitle_path is not None and zh_subtitle_path is not None

        return {
            "video_path": str(video_path),
            "audio_path": str(audio_path) if extract_audio else None,
            "subtitle_path": str(subtitle_path) if subtitle_path else None,
            "has_youtube_subtitles": subtitle_path is not None,
            "zh_subtitle_path": str(zh_subtitle_path) if zh_subtitle_path else None,
            "has_bilingual_youtube_subs": has_bilingual,
            "title": info.get("title"),
            "duration": duration,
            "channel": info.get("channel") or info.get("uploader"),
            "description": info.get("description"),
        }

    def _is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube video."""
        url_lower = url.lower()
        return "youtube.com" in url_lower or "youtu.be" in url_lower

    async def _handle_local_file(
        self,
        url: str,
        source_dir: Path,
        audio_path: Path,
        extract_audio: bool,
    ) -> Dict[str, Any]:
        """
        Handle locally uploaded files (file:// URLs).

        The file is already uploaded and saved by the upload endpoint.
        We just need to verify it exists and extract audio if requested.
        """
        # Parse file:// URL to get the actual path
        file_path = Path(url.replace("file://", ""))

        if not file_path.exists():
            raise FileNotFoundError(f"Uploaded video file not found: {file_path}")

        logger.info(f"Using locally uploaded file: {file_path}")

        # Get video metadata (duration + title) using ffprobe
        metadata = await self._get_video_metadata(file_path)
        duration = metadata["duration"]

        # Check duration limit
        if duration > self.max_duration:
            raise ValueError(
                f"Video duration ({duration}s) exceeds maximum ({self.max_duration}s)"
            )

        # Title priority: ffprobe metadata title → filename stem
        title = metadata["title"] or file_path.stem

        # Extract audio if requested
        if extract_audio:
            if audio_path.exists():
                logger.info("Audio already exists, skipping extraction")
            else:
                logger.info("Extracting audio from uploaded video...")
                await self._extract_audio(file_path, audio_path)

        return {
            "video_path": str(file_path),
            "audio_path": str(audio_path) if extract_audio else None,
            "subtitle_path": None,
            "has_youtube_subtitles": False,
            "title": title,
            "duration": duration,
            "channel": None,
            "description": None,
        }

    async def _get_video_metadata(self, video_path: Path) -> Dict[str, Any]:
        """Get video duration and title using ffprobe."""
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration:format_tags=title",
            "-of", "json",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"ffprobe failed: {result.stderr}")
            return {"duration": 0.0, "title": None}

        try:
            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            duration = float(fmt.get("duration", 0))
            title = fmt.get("tags", {}).get("title")
            return {"duration": duration, "title": title}
        except (json.JSONDecodeError, ValueError):
            return {"duration": 0.0, "title": None}

    async def _get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video metadata without downloading."""
        # Try different player clients for metadata extraction
        client_options = [
            [],  # Default
            ["--extractor-args", "youtube:player_client=ios"],
        ]

        for extra_args in client_options:
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-download",
            ] + extra_args + [url]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                return json.loads(result.stdout)

            # If 403/SABR error, try next client
            if "403" in result.stderr or "SABR" in result.stderr:
                continue

        # If all clients fail, raise with last error
        raise RuntimeError(f"yt-dlp info extraction failed: {result.stderr}")

    async def _download_video(self, url: str, output_path: Path) -> None:
        """Download video to specified path."""
        # Base command with format selection
        # Using format that works better with YouTube's SABR streaming restrictions
        base_cmd = [
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", str(output_path),
            "--no-playlist",
        ]

        # Try different player clients if the default fails
        # iOS/Android clients often work when web clients fail due to SABR
        client_options = [
            [],  # Default (uses deno JS runtime if available)
            ["--extractor-args", "youtube:player_client=ios"],
            ["--extractor-args", "youtube:player_client=android"],
            ["--extractor-args", "youtube:player_client=tv"],
        ]

        last_error = None
        for extra_args in client_options:
            cmd = base_cmd + extra_args + [url]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0 and output_path.exists():
                return  # Success

            last_error = result.stderr
            # Check if it's a format/SABR error worth retrying with different client
            if "403" in result.stderr or "SABR" in result.stderr:
                logger.warning(f"yt-dlp failed with client args {extra_args}, trying next...")
                continue
            else:
                # Other error, don't retry
                break

        raise RuntimeError(f"yt-dlp failed: {last_error}")

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
        prefer_auto: bool = False,
    ) -> Optional[Path]:
        """
        Download subtitles from YouTube.

        Args:
            url: Video URL
            output_dir: Directory to save subtitle file
            langs: List of language codes to try (e.g., ["en", "en-US"])
            prefer_auto: If True, try auto-generated subs first

        Returns:
            Path to subtitle file if successful, None otherwise
        """
        # Order: manual first (default), or auto first if prefer_auto
        attempts = [True, False] if prefer_auto else [False, True]
        for write_auto in attempts:
            subtitle_path = output_dir / "subtitle.en.vtt"

            # Use wildcard patterns to match language variants (en, en-US, en-GB, etc.)
            sub_lang_patterns = []
            for lang in langs:
                sub_lang_patterns.append(lang)
                sub_lang_patterns.append(f"{lang}-*")
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--sub-format", "vtt",
                "--sub-langs", ",".join(sub_lang_patterns),
                "-o", str(output_dir / "subtitle"),
            ]

            if write_auto:
                cmd.append("--write-auto-subs")
            else:
                cmd.append("--write-subs")

            cmd.append(url)

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Check for downloaded subtitle file (yt-dlp adds language suffix)
            # Match exact lang and variants like en-US, en-GB, etc.
            import glob as glob_mod
            for lang in langs:
                possible_paths = [
                    output_dir / f"subtitle.{lang}.vtt",
                ]
                # Also glob for variants like subtitle.en-US.vtt
                possible_paths.extend(
                    Path(p) for p in glob_mod.glob(str(output_dir / f"subtitle.{lang}-*.vtt"))
                )
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

        with open(subtitle_path, "r", encoding="utf-8") as f:
            content = f.read()

        logger.debug(f"VTT file size: {len(content)} chars, first 500: {content[:500]}")

        # Line-by-line parsing (most reliable for various VTT formats)
        lines = content.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Look for timestamp line (contains "-->")
            if "-->" in line:
                # Extract timestamps, handling various formats:
                # 00:00:00.000 --> 00:00:05.000
                # 00:00.000 --> 00:05.000
                # 00:00:00.000 --> 00:00:05.000 align:start position:0%
                parts = line.split("-->")
                if len(parts) == 2:
                    # Get first token of each part (timestamp)
                    start_str = parts[0].strip().split()[0] if parts[0].strip() else ""
                    # For end, get first token that looks like a timestamp
                    end_part = parts[1].strip()
                    end_tokens = end_part.split()
                    end_str = end_tokens[0] if end_tokens else ""

                    # Collect text until empty line or next timestamp
                    text_lines = []
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        # Stop at empty line or timestamp line
                        if not next_line.strip() or "-->" in next_line:
                            break
                        # Skip lines that look like cue identifiers (just numbers)
                        if not next_line.strip().isdigit():
                            text_lines.append(next_line.strip())
                        i += 1

                    text = " ".join(text_lines)
                    # Clean up text
                    text = re.sub(r"<[^>]+>", "", text)  # Remove HTML/VTT tags
                    text = html.unescape(text)  # Decode HTML entities (&gt;&gt; → >>)
                    text = re.sub(r">>\s*", "", text)  # Remove >> speaker change markers
                    text = re.sub(r"\s+", " ", text).strip()  # Normalize whitespace

                    if text and start_str and end_str:
                        try:
                            start = self._parse_vtt_timestamp(start_str)
                            end = self._parse_vtt_timestamp(end_str)
                            segments.append({
                                "start": start,
                                "end": end,
                                "text": text,
                                "speaker": "SPEAKER_00",
                            })
                        except Exception as e:
                            logger.warning(f"Failed to parse timestamp '{start_str}' -> '{end_str}': {e}")
                    continue
            i += 1

        # Merge consecutive segments with same text (YouTube often duplicates)
        merged = []
        for seg in segments:
            if merged and merged[-1]["text"] == seg["text"]:
                # Extend previous segment
                merged[-1]["end"] = seg["end"]
            else:
                merged.append(seg)

        logger.info(f"Parsed {len(merged)} segments from YouTube subtitles (raw: {len(segments)})")
        return merged

    async def _download_zh_subtitles(
        self,
        url: str,
        output_dir: Path,
        info: Dict[str, Any],
        prefer_auto: bool = False,
    ) -> Optional[Path]:
        """
        Download Chinese subtitles from YouTube.

        Tries zh-Hans, zh-Hant, zh in order from manual subs first,
        then auto-generated if prefer_auto or no manual found.

        Returns:
            Path to Chinese VTT file if successful, None otherwise
        """
        zh_langs = ["zh-Hans", "zh-Hant", "zh"]
        manual_subs = info.get("subtitles", {})
        auto_subs = info.get("automatic_captions", {})

        # Check which ZH languages are available
        manual_zh = [lang for lang in zh_langs if lang in manual_subs]
        auto_zh = [lang for lang in zh_langs if lang in auto_subs]

        if not manual_zh and not auto_zh:
            return None

        # Order: manual first (unless prefer_auto), then auto
        attempts = []
        if prefer_auto:
            if auto_zh:
                attempts.append((auto_zh, True))
            if manual_zh:
                attempts.append((manual_zh, False))
        else:
            if manual_zh:
                attempts.append((manual_zh, False))
            if auto_zh:
                attempts.append((auto_zh, True))

        for langs, write_auto in attempts:
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--sub-format", "vtt",
                "--sub-langs", ",".join(langs),
                "-o", str(output_dir / "subtitle_zh"),
            ]

            if write_auto:
                cmd.append("--write-auto-subs")
            else:
                cmd.append("--write-subs")

            cmd.append(url)

            subprocess.run(cmd, capture_output=True, text=True)

            # Check for downloaded file
            for lang in langs:
                possible_paths = [
                    output_dir / f"subtitle_zh.{lang}.vtt",
                    output_dir / f"subtitle_zh.{lang.split('-')[0]}.vtt",
                ]
                for path in possible_paths:
                    if path.exists():
                        final_path = output_dir / "youtube_subtitle_zh.vtt"
                        path.rename(final_path)
                        return final_path

        return None

    def merge_bilingual_subtitles(
        self,
        en_segments: List[Dict[str, Any]],
        zh_segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Merge EN and ZH subtitle segments using EN-anchored overlap matching.

        For each EN segment, finds all overlapping ZH segments and concatenates
        their text. Uses sliding window pointer for O(n+m) efficiency.

        Args:
            en_segments: List of EN segments with start, end, text, speaker
            zh_segments: List of ZH segments with start, end, text

        Returns:
            List of merged segments with text (EN), translation (ZH), start, end, speaker
        """
        merged = []
        zh_ptr = 0  # Sliding window start pointer

        for en_seg in en_segments:
            en_start = en_seg["start"]
            en_end = en_seg["end"]

            # Advance pointer past ZH segments that end before this EN segment starts
            while zh_ptr < len(zh_segments) and zh_segments[zh_ptr]["end"] <= en_start:
                zh_ptr += 1

            # Collect all overlapping ZH segments
            zh_texts = []
            j = zh_ptr
            while j < len(zh_segments):
                zh_seg = zh_segments[j]
                zh_start = zh_seg["start"]
                zh_end = zh_seg["end"]

                # No overlap if ZH starts after EN ends
                if zh_start >= en_end:
                    break

                # Overlap exists: zh_start < en_end AND zh_end > en_start
                if zh_end > en_start:
                    zh_texts.append(zh_seg["text"])

                j += 1

            merged.append({
                "start": en_start,
                "end": en_end,
                "text": en_seg["text"],
                "translation": " ".join(zh_texts) if zh_texts else "",
                "speaker": en_seg.get("speaker", "SPEAKER_00"),
            })

        return merged

    def _parse_vtt_timestamp(self, ts: str) -> float:
        """Parse VTT timestamp to seconds. Handles HH:MM:SS.mmm and MM:SS.mmm formats."""
        ts = ts.strip()
        parts = ts.split(":")

        if len(parts) == 3:
            # HH:MM:SS.mmm
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            # MM:SS.mmm
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        else:
            # Try parsing as just seconds
            return float(ts)
