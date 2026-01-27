"""Export worker for video rendering with bilingual subtitles."""

import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from loguru import logger

from app.config import settings
from app.models.timeline import EditableSegment, ExportProfile, SegmentState, Timeline


# ASS subtitle template with bilingual style (both at bottom, English above Chinese)
# Alignment: 2 = bottom center
# English: smaller font (44), white text, gray outline, positioned higher (MarginV=120)
# Chinese: larger font (52), yellow text, positioned lower (MarginV=30)
ASS_HEADER = """[Script Info]
Title: Hardcore Player Bilingual Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: English,Arial,44,&H00FFFFFF,&H000000FF,&H00404040,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,20,20,120,1
Style: Chinese,Microsoft YaHei,52,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,30,1

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


class ExportWorker:
    """Worker for exporting videos with bilingual subtitles."""

    def __init__(self):
        self.use_nvenc = settings.ffmpeg_nvenc

    async def generate_ass(
        self,
        segments: List[EditableSegment],
        output_path: Path,
        use_traditional: bool = True,
        time_offset: float = 0.0,
    ) -> Path:
        """Generate ASS subtitle file from segments.

        Args:
            segments: List of editable segments
            output_path: Path to save ASS file
            use_traditional: Use Traditional Chinese
            time_offset: Time offset to apply to all timestamps (for essence export)

        Returns:
            Path to ASS file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert Simplified to Traditional if needed
        converter = None
        if use_traditional:
            try:
                import opencc
                converter = opencc.OpenCC("s2t")
            except ImportError:
                logger.warning("opencc not installed, using Simplified Chinese")

        lines = [ASS_HEADER]

        for seg in segments:
            # Apply time offset
            start = _seconds_to_ass_time(seg.effective_start - time_offset)
            end = _seconds_to_ass_time(seg.effective_end - time_offset)

            # English subtitle (top, white)
            english_text = seg.en.replace("\n", "\\N")
            if english_text:
                lines.append(f"Dialogue: 0,{start},{end},English,,0,0,0,,{english_text}")

            # Chinese subtitle (bottom, yellow)
            chinese_text = seg.zh.replace("\n", "\\N")
            if chinese_text:
                if converter:
                    chinese_text = converter.convert(chinese_text)
                lines.append(f"Dialogue: 0,{start},{end},Chinese,,0,0,0,,{chinese_text}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated ASS subtitle: {output_path}")
        return output_path

    def _get_video_dimensions(self, video_path: Path) -> Tuple[int, int]:
        """Get video width and height using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"ffprobe failed, using default 1920x1080: {result.stderr}")
            return 1920, 1080
        try:
            w, h = result.stdout.strip().split("x")
            return int(w), int(h)
        except Exception:
            return 1920, 1080

    def _hex_to_ass_color(self, hex_color: str, opacity: int = 0) -> str:
        """Convert hex color (#RRGGBB) to ASS format (&HAABBGGRR).

        Args:
            hex_color: Hex color string like "#ffffff" or "#facc15"
            opacity: Opacity value 0-255 (0=opaque, 255=transparent)

        Returns:
            ASS color string like "&H00FFFFFF"
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            # ASS uses AABBGGRR format (reversed RGB + alpha)
            return f"&H{opacity:02X}{b:02X}{g:02X}{r:02X}"
        return "&H00FFFFFF"  # Default white

    async def generate_ass_with_layout(
        self,
        segments: List[EditableSegment],
        output_path: Path,
        use_traditional: bool = True,
        time_offset: float = 0.0,
        video_height: int = 1080,
        subtitle_area_ratio: float = 0.5,
        subtitle_style=None,
    ) -> Path:
        """Generate ASS subtitle file with WYSIWYG layout (video on top, subtitles at bottom).

        Args:
            segments: List of editable segments
            output_path: Path to save ASS file
            use_traditional: Use Traditional Chinese
            time_offset: Time offset for timestamps
            video_height: Total video height
            subtitle_area_ratio: Ratio of subtitle area (0.3-0.7)
            subtitle_style: Optional subtitle style options (font size, colors, etc.)

        Returns:
            Path to ASS file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Calculate subtitle area dimensions
        subtitle_area_height = int(video_height * subtitle_area_ratio)

        # Get style options (from request or defaults)
        # Default font sizes are 40px (matching frontend default)
        base_en_size = 40
        base_zh_size = 40
        en_color_hex = "#ffffff"
        zh_color_hex = "#facc15"
        bg_color_hex = "#1a2744"

        if subtitle_style:
            base_en_size = getattr(subtitle_style, 'en_font_size', 40) or 40
            base_zh_size = getattr(subtitle_style, 'zh_font_size', 40) or 40
            en_color_hex = getattr(subtitle_style, 'en_color', "#ffffff") or "#ffffff"
            zh_color_hex = getattr(subtitle_style, 'zh_color', "#facc15") or "#facc15"
            bg_color_hex = getattr(subtitle_style, 'background_color', "#1a2744") or "#1a2744"

        # Scale font sizes based on subtitle area height
        # Base reference: 40px at 300px subtitle height
        scale_factor = subtitle_area_height / 300
        english_font_size = max(24, int(base_en_size * scale_factor))
        chinese_font_size = max(24, int(base_zh_size * scale_factor))

        # Calculate vertical positions to center both subtitles as a group
        gap_between = int(20 * scale_factor)  # Gap between English and Chinese
        total_block_height = english_font_size + gap_between + chinese_font_size

        # Center the block in subtitle area
        block_bottom = (subtitle_area_height - total_block_height) // 2
        chinese_margin_v = max(10, block_bottom)
        english_margin_v = chinese_margin_v + chinese_font_size + gap_between

        # Convert colors to ASS format
        english_color = self._hex_to_ass_color(en_color_hex, 0)
        chinese_color = self._hex_to_ass_color(zh_color_hex, 0)
        background_color = self._hex_to_ass_color(bg_color_hex, 192)  # 75% opacity (192/255)

        # ASS header with calculated positions
        # BorderStyle=3: Opaque box (背景框)
        # Outline=12: Padding around text
        ass_header = f"""[Script Info]
Title: Hardcore Player Bilingual Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: English,Arial,{english_font_size},{english_color},&H000000FF,{background_color},{background_color},0,0,0,0,100,100,0,0,3,12,0,2,40,40,{english_margin_v},1
Style: Chinese,Microsoft YaHei,{chinese_font_size},{chinese_color},&H000000FF,{background_color},{background_color},-1,0,0,0,100,100,0,0,3,12,0,2,40,40,{chinese_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

        # Convert Simplified to Traditional if needed
        converter = None
        if use_traditional:
            try:
                import opencc
                converter = opencc.OpenCC("s2t")
            except ImportError:
                logger.warning("opencc not installed, using Simplified Chinese")

        lines = [ass_header]

        for seg in segments:
            start = _seconds_to_ass_time(seg.effective_start - time_offset)
            end = _seconds_to_ass_time(seg.effective_end - time_offset)

            english_text = seg.en.replace("\n", "\\N")
            if english_text:
                lines.append(f"Dialogue: 0,{start},{end},English,,0,0,0,,{english_text}")

            chinese_text = seg.zh.replace("\n", "\\N")
            if chinese_text:
                if converter:
                    chinese_text = converter.convert(chinese_text)
                lines.append(f"Dialogue: 0,{start},{end},Chinese,,0,0,0,,{chinese_text}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated ASS subtitle with layout: {output_path}")
        return output_path

    async def export_full_video(
        self,
        timeline: Timeline,
        video_path: Path,
        output_path: Path,
        subtitle_style=None,
    ) -> Path:
        """Export full video with WYSIWYG layout (scaled video + subtitle area).

        Layout:
        ┌─────────────────────┐
        │   Scaled Video      │  ← (1 - subtitle_area_ratio) of height
        │                     │
        ├─────────────────────┤
        │   English subtitle  │  ← subtitle_area_ratio of height
        │   中文字幕           │
        └─────────────────────┘

        Args:
            timeline: Timeline with all segments
            video_path: Source video path
            output_path: Output video path

        Returns:
            Path to exported video
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get video-level trim settings
        trim_start = getattr(timeline, 'video_trim_start', 0.0) or 0.0
        trim_end = getattr(timeline, 'video_trim_end', None)

        # Get video dimensions
        orig_width, orig_height = self._get_video_dimensions(video_path)
        subtitle_ratio = getattr(timeline, 'subtitle_area_ratio', 0.5)

        # Calculate video area height (top portion)
        video_area_height = int(orig_height * (1 - subtitle_ratio))

        # Filter segments to only include those within trim range
        if trim_start > 0 or trim_end is not None:
            effective_trim_end = trim_end if trim_end is not None else float('inf')
            trimmed_segments = [
                seg for seg in timeline.segments
                if seg.start >= trim_start and seg.end <= effective_trim_end
            ]
            # Adjust segment timestamps relative to trim_start
            time_offset = trim_start
        else:
            trimmed_segments = timeline.segments
            time_offset = 0.0

        # Generate ASS subtitle file with WYSIWYG layout
        ass_path = output_path.parent / "subtitles_full.ass"
        await self.generate_ass_with_layout(
            segments=trimmed_segments,
            output_path=ass_path,
            use_traditional=timeline.use_traditional_chinese,
            time_offset=time_offset,
            video_height=orig_height,
            subtitle_area_ratio=subtitle_ratio,
            subtitle_style=subtitle_style,
        )

        # Escape special characters in path for ffmpeg filter
        ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")

        # Calculate scaled video dimensions while maintaining aspect ratio
        # The video should fit within the video area (top portion)
        orig_aspect = orig_width / orig_height
        target_aspect = orig_width / video_area_height

        if orig_aspect >= target_aspect:
            # Video is wider than target area - scale by width, center vertically
            scaled_width = orig_width
            scaled_height = int(orig_width / orig_aspect)
        else:
            # Video is taller than target area - scale by height, center horizontally
            scaled_height = video_area_height
            scaled_width = int(video_area_height * orig_aspect)

        logger.info(
            f"WYSIWYG export: original={orig_width}x{orig_height}, "
            f"video_area={orig_width}x{video_area_height}, "
            f"scaled={scaled_width}x{scaled_height}"
        )

        # Build ffmpeg filter:
        # 1. Scale video maintaining aspect ratio
        # 2. Pad with dark blue background (#1a2744) to match review page
        # 3. Overlay subtitles
        # Note: FFmpeg color format is 0xRRGGBB
        subtitle_bg_color = "0x1a2744"  # Dark blue matching review page
        vf_filter = (
            f"scale={scaled_width}:{scaled_height},"
            f"pad={orig_width}:{orig_height}:(ow-iw)/2:0:{subtitle_bg_color},"
            f"setsar=1,"
            f"ass={ass_path_escaped}"
        )

        # Build ffmpeg command with trim support
        cmd = ["ffmpeg"]

        # Add seek option if trim start is set (faster when placed before -i)
        if trim_start > 0:
            cmd.extend(["-ss", str(trim_start)])

        cmd.extend(["-i", str(video_path)])

        # Add duration limit if trim end is set
        if trim_end is not None:
            duration = trim_end - trim_start
            cmd.extend(["-t", str(duration)])

        cmd.extend(["-vf", vf_filter])

        if self.use_nvenc:
            cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "23"])

        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-y", str(output_path)])

        trim_info = ""
        if trim_start > 0 or trim_end is not None:
            trim_info = f", trim={trim_start:.1f}s-{trim_end or 'end'}"
        logger.info(f"Exporting full video with WYSIWYG layout (ratio={subtitle_ratio}{trim_info}): {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg export failed: {result.stderr}")

        logger.info(f"Full video exported: {output_path}")
        return output_path

    async def export_essence(
        self,
        timeline: Timeline,
        video_path: Path,
        output_path: Path,
        subtitle_style=None,
    ) -> Path:
        """Export essence video (only KEEP segments) with subtitles.

        This method:
        1. Extracts KEEP segments from source video
        2. Concatenates them with ffmpeg
        3. Generates re-timed ASS subtitles
        4. Burns subtitles into final video

        Args:
            timeline: Timeline with segments (uses KEEP segments only)
            video_path: Source video path
            output_path: Output video path

        Returns:
            Path to exported essence video
        """
        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get video-level trim settings
        trim_start = getattr(timeline, 'video_trim_start', 0.0) or 0.0
        trim_end = getattr(timeline, 'video_trim_end', None)
        effective_trim_end = trim_end if trim_end is not None else float('inf')

        # Get KEEP segments that are within the trim range
        keep_segments = [
            seg for seg in timeline.segments
            if seg.state == SegmentState.KEEP
            and seg.start >= trim_start
            and seg.end <= effective_trim_end
        ]

        if not keep_segments:
            raise ValueError("No KEEP segments within trim range to export")

        # Create temp directory for segment clips
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract each KEEP segment
            segment_files = []
            for i, seg in enumerate(keep_segments):
                segment_file = temp_path / f"segment_{i:04d}.mp4"
                await self._extract_segment(
                    video_path=video_path,
                    start=seg.effective_start,
                    duration=seg.effective_duration,
                    output_path=segment_file,
                )
                segment_files.append(segment_file)

            # Create concat file
            concat_file = temp_path / "concat.txt"
            with open(concat_file, "w") as f:
                for segment_file in segment_files:
                    f.write(f"file '{segment_file}'\n")

            # Concatenate segments
            concat_output = temp_path / "concat.mp4"
            await self._concat_segments(concat_file, concat_output)

            # Generate re-timed ASS subtitles for essence
            # We need to recalculate timing based on concatenated positions
            retimed_segments = self._retime_segments(keep_segments)
            ass_path = output_path.parent / "subtitles_essence.ass"
            await self._generate_essence_ass(
                retimed_segments,
                ass_path,
                timeline.use_traditional_chinese,
            )

            # Burn subtitles into concatenated video
            ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")

            cmd = [
                "ffmpeg",
                "-i", str(concat_output),
                "-vf", f"ass={ass_path_escaped}",
            ]

            if self.use_nvenc:
                cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "23"])

            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-y", str(output_path)])

            logger.info(f"Burning subtitles into essence video: {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg essence export failed: {result.stderr}")

        logger.info(
            f"Essence video exported: {output_path} "
            f"({len(keep_segments)} segments, {timeline.keep_duration:.1f}s)"
        )
        return output_path

    async def export(
        self,
        timeline: Timeline,
        video_path: Path,
        output_dir: Path,
        subtitle_style=None,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """Export video(s) based on timeline export profile.

        Args:
            timeline: Timeline with export settings
            video_path: Source video path
            output_dir: Directory for output files
            subtitle_style: Optional subtitle style options

        Returns:
            Tuple of (full_video_path, essence_video_path)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        full_path = None
        essence_path = None

        profile = timeline.export_profile

        if profile in (ExportProfile.FULL, ExportProfile.BOTH):
            full_path = output_dir / "full_subtitled.mp4"
            await self.export_full_video(timeline, video_path, full_path, subtitle_style)

        if profile in (ExportProfile.ESSENCE, ExportProfile.BOTH):
            essence_path = output_dir / "essence.mp4"
            await self.export_essence(timeline, video_path, essence_path, subtitle_style)

        return full_path, essence_path

    async def _extract_segment(
        self,
        video_path: Path,
        start: float,
        duration: float,
        output_path: Path,
    ) -> None:
        """Extract a segment from video using ffmpeg."""
        cmd = [
            "ffmpeg",
            "-ss", str(start),
            "-i", str(video_path),
            "-t", str(duration),
            "-c:v", "copy",
            "-c:a", "copy",
            "-avoid_negative_ts", "make_zero",
            "-y", str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg segment extraction failed: {result.stderr}")

    async def _concat_segments(
        self,
        concat_file: Path,
        output_path: Path,
    ) -> None:
        """Concatenate video segments using ffmpeg."""
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c:v", "copy",
            "-c:a", "copy",
            "-y", str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")

    def _retime_segments(
        self,
        segments: List[EditableSegment],
    ) -> List[Tuple[float, float, str, str]]:
        """Retime segments for concatenated video.

        Returns list of (start, end, en, zh) tuples with new timing.
        """
        retimed = []
        current_time = 0.0

        for seg in segments:
            duration = seg.effective_duration
            retimed.append((
                current_time,
                current_time + duration,
                seg.en,
                seg.zh,
            ))
            current_time += duration

        return retimed

    async def _generate_essence_ass(
        self,
        retimed_segments: List[Tuple[float, float, str, str]],
        output_path: Path,
        use_traditional: bool = True,
    ) -> Path:
        """Generate ASS subtitles for retimed essence segments."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert Simplified to Traditional if needed
        converter = None
        if use_traditional:
            try:
                import opencc
                converter = opencc.OpenCC("s2t")
            except ImportError:
                logger.warning("opencc not installed, using Simplified Chinese")

        lines = [ASS_HEADER]

        for start, end, en, zh in retimed_segments:
            start_str = _seconds_to_ass_time(start)
            end_str = _seconds_to_ass_time(end)

            # English subtitle (top, white)
            english_text = en.replace("\n", "\\N")
            if english_text:
                lines.append(f"Dialogue: 0,{start_str},{end_str},English,,0,0,0,,{english_text}")

            # Chinese subtitle (bottom, yellow)
            chinese_text = zh.replace("\n", "\\N")
            if chinese_text:
                if converter:
                    chinese_text = converter.convert(chinese_text)
                lines.append(f"Dialogue: 0,{start_str},{end_str},Chinese,,0,0,0,,{chinese_text}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated essence ASS subtitle: {output_path}")
        return output_path
