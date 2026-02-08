"""Export worker for video rendering with bilingual subtitles."""

import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
from loguru import logger

from app.config import settings
from app.models.timeline import EditableSegment, ExportProfile, PinnedCard, SegmentState, SubtitleLanguageMode, SubtitleStyleMode, Timeline
from app.workers.subtitle_styles import (
    SubtitleStyleConfig,
    SubtitleStyleMode as StyleMode,
    generate_half_screen_ass_header,
    generate_floating_ass_header,
    generate_ass_header,
    ASS_HEADER_DEFAULT,
)

# Card overlay constants
CARD_PANEL_WIDTH = 400  # Width of card panel on right side
CARD_ANIMATION_DURATION = 0.3  # Slide/fade duration in seconds


# ASS subtitle template with bilingual style (both at bottom, English above Chinese)
# Alignment: 2 = bottom center
# In ASS bottom alignment, SMALLER MarginV = closer to bottom edge = lower on screen
# English: smaller font (44), white text, gray outline, positioned higher (MarginV=30 = higher position)
# Chinese: larger font (52), yellow text, positioned lower (MarginV=120 = lower position)
ASS_HEADER = """[Script Info]
Title: SceneMind Bilingual Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: English,Arial,44,&H00FFFFFF,&H000000FF,&H00404040,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,20,20,30,1
Style: Chinese,Microsoft YaHei,52,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,1,2,20,20,120,1

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
        self._card_renderer = None

    def _get_card_renderer(self):
        """Lazy load card renderer."""
        if self._card_renderer is None:
            try:
                from app.workers.card_renderer import CardRenderer
                self._card_renderer = CardRenderer()
            except Exception as e:
                logger.warning(f"Card renderer not available: {e}")
        return self._card_renderer

    async def render_pinned_cards(
        self,
        pinned_cards: List[PinnedCard],
        output_dir: Path,
        time_offset: float = 0.0,
    ) -> List[Tuple[Path, float, float]]:
        """Render pinned cards to PNG images.

        Args:
            pinned_cards: List of pinned cards
            output_dir: Directory to save card images
            time_offset: Time offset for card timing

        Returns:
            List of (image_path, display_start, display_end) tuples
        """
        renderer = self._get_card_renderer()
        if not renderer:
            logger.warning("Card renderer not available, skipping card rendering")
            return []

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        rendered_cards = []
        for i, card in enumerate(pinned_cards):
            if not card.card_data:
                logger.warning(f"Card {card.id} has no data, skipping")
                continue

            card_path = output_dir / f"card_{i:03d}_{card.id}.png"
            try:
                renderer.render_pinned_card(
                    card_data=card.card_data,
                    card_type=card.card_type.value if hasattr(card.card_type, 'value') else card.card_type,
                    output_path=card_path,
                )

                # Adjust timing with offset
                display_start = max(0, card.display_start - time_offset)
                display_end = max(0, card.display_end - time_offset)

                if display_end > display_start:
                    rendered_cards.append((card_path, display_start, display_end))
                    logger.debug(
                        f"Rendered card {card.id} ({card.card_type}): "
                        f"{display_start:.1f}s - {display_end:.1f}s"
                    )
            except Exception as e:
                logger.error(f"Failed to render card {card.id}: {e}")

        logger.info(f"Rendered {len(rendered_cards)} pinned cards")
        return rendered_cards

    def _build_card_overlay_filter(
        self,
        cards: List[Tuple[Path, float, float]],
        video_width: int,
        video_height: int,
        card_panel_width: int = CARD_PANEL_WIDTH,
    ) -> Tuple[str, List[str]]:
        """Build FFmpeg filter for card overlays with slide-in animation.

        Animation: Cards slide in from right with fade-in (300ms), hold, then fade-out.

        Args:
            cards: List of (image_path, start_time, end_time) tuples
            video_width: Video width
            video_height: Video height
            card_panel_width: Width of card panel area

        Returns:
            Tuple of (filter_complex string, list of input arguments)
        """
        if not cards:
            return "", []

        input_args = []
        filters = []

        # Card position: right side, centered vertically
        card_x = video_width - card_panel_width - 20  # 20px margin from right
        card_y_base = 100  # Top margin

        for i, (card_path, start, end) in enumerate(cards):
            input_idx = i + 1  # 0 is video input
            input_args.extend(["-i", str(card_path)])

            # Animation parameters
            fade_in_duration = CARD_ANIMATION_DURATION
            fade_out_duration = CARD_ANIMATION_DURATION
            slide_distance = 50  # Pixels to slide

            # FFmpeg overlay with animation expressions:
            # - Slide in from right: x starts at card_x + slide_distance, moves to card_x
            # - Fade in: alpha goes from 0 to 1
            # - Fade out: alpha goes from 1 to 0 at end

            # Time expressions for animation phases
            t_start = start
            t_fade_in_end = start + fade_in_duration
            t_fade_out_start = end - fade_out_duration
            t_end = end

            # X position expression (slide from right)
            # During fade-in: x = card_x + slide_distance * (1 - progress)
            # After fade-in: x = card_x
            x_expr = (
                f"if(lt(t,{t_start}),{card_x + slide_distance},"
                f"if(lt(t,{t_fade_in_end}),"
                f"{card_x}+{slide_distance}*(1-(t-{t_start})/{fade_in_duration}),"
                f"{card_x}))"
            )

            # Enable expression (visible during display window)
            enable_expr = f"between(t,{t_start},{t_end})"

            # Alpha expression for fade in/out
            # During fade-in: alpha = (t - start) / fade_duration
            # During hold: alpha = 1
            # During fade-out: alpha = (end - t) / fade_duration
            alpha_expr = (
                f"if(lt(t,{t_fade_in_end}),"
                f"(t-{t_start})/{fade_in_duration},"
                f"if(lt(t,{t_fade_out_start}),1,"
                f"({t_end}-t)/{fade_out_duration}))"
            )

            # Build filter for this card
            if i == 0:
                # First card overlays on video
                filters.append(
                    f"[0:v][{input_idx}:v]overlay="
                    f"x='{x_expr}':y={card_y_base}:"
                    f"enable='{enable_expr}':"
                    f"format=auto"
                    f"[v{i}]"
                )
            else:
                # Subsequent cards overlay on previous result
                filters.append(
                    f"[v{i-1}][{input_idx}:v]overlay="
                    f"x='{x_expr}':y={card_y_base}:"
                    f"enable='{enable_expr}':"
                    f"format=auto"
                    f"[v{i}]"
                )

        # Final output label
        final_label = f"v{len(cards) - 1}" if cards else "0:v"

        filter_complex = ";".join(filters)
        return filter_complex, input_args, final_label

    async def generate_ass(
        self,
        segments: List[EditableSegment],
        output_path: Path,
        use_traditional: bool = True,
        time_offset: float = 0.0,
        subtitle_language_mode: SubtitleLanguageMode = SubtitleLanguageMode.BOTH,
    ) -> Path:
        """Generate ASS subtitle file from segments.

        Args:
            segments: List of editable segments
            output_path: Path to save ASS file
            use_traditional: Use Traditional Chinese
            time_offset: Time offset to apply to all timestamps (for essence export)
            subtitle_language_mode: Which subtitles to include (both, en, zh, none)

        Returns:
            Path to ASS file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # If mode is NONE, return empty ASS file
        if subtitle_language_mode == SubtitleLanguageMode.NONE:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("")
            logger.info(f"Generated empty ASS subtitle (language_mode=none): {output_path}")
            return output_path

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
            # Skip dropped segments
            if seg.state == SegmentState.DROP:
                continue
            # Apply time offset
            start = _seconds_to_ass_time(seg.effective_start - time_offset)
            end = _seconds_to_ass_time(seg.effective_end - time_offset)

            # English subtitle (top, white) - include if mode is BOTH or EN
            if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.EN):
                english_text = seg.en.replace("\n", "\\N")
                if english_text:
                    lines.append(f"Dialogue: 0,{start},{end},English,,0,0,0,,{english_text}")

            # Chinese subtitle (bottom, yellow) - include if mode is BOTH or ZH
            if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.ZH):
                chinese_text = seg.zh.replace("\n", "\\N")
                if chinese_text:
                    if converter:
                        chinese_text = converter.convert(chinese_text)
                    lines.append(f"Dialogue: 0,{start},{end},Chinese,,0,0,0,,{chinese_text}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated ASS subtitle (language_mode={subtitle_language_mode.value}): {output_path}")
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
        subtitle_area_ratio: float = 0.3,
        subtitle_style=None,
        subtitle_style_mode: SubtitleStyleMode = SubtitleStyleMode.HALF_SCREEN,
        subtitle_language_mode: SubtitleLanguageMode = SubtitleLanguageMode.BOTH,
    ) -> Path:
        """Generate ASS subtitle file with appropriate style based on mode.

        Args:
            segments: List of editable segments
            output_path: Path to save ASS file
            use_traditional: Use Traditional Chinese
            time_offset: Time offset for timestamps
            video_height: Total video height
            subtitle_area_ratio: Ratio of subtitle area (for half_screen mode)
            subtitle_style: Optional subtitle style options (font size, colors, etc.)
            subtitle_style_mode: Subtitle rendering mode (half_screen, floating, none)
            subtitle_language_mode: Which subtitles to include (both, en, zh, none)

        Returns:
            Path to ASS file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build SubtitleStyleConfig from request options
        config = SubtitleStyleConfig()
        if subtitle_style:
            config.en_font_size = getattr(subtitle_style, 'en_font_size', 40) or 40
            config.zh_font_size = getattr(subtitle_style, 'zh_font_size', 40) or 40
            config.en_color = getattr(subtitle_style, 'en_color', "#ffffff") or "#ffffff"
            config.zh_color = getattr(subtitle_style, 'zh_color', "#facc15") or "#facc15"
            config.background_color = getattr(subtitle_style, 'background_color', "#1a2744") or "#1a2744"

        # Generate ASS header based on mode using subtitle_styles module
        # Convert model enum to styles enum
        style_mode = StyleMode(subtitle_style_mode.value)
        ass_header = generate_ass_header(
            mode=style_mode,
            video_height=video_height,
            subtitle_area_ratio=subtitle_area_ratio,
            config=config,
        )

        # If style mode is NONE or language mode is NONE, return empty ASS file
        if subtitle_style_mode == SubtitleStyleMode.NONE or subtitle_language_mode == SubtitleLanguageMode.NONE:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("")
            logger.info(f"Generated empty ASS subtitle (style_mode={subtitle_style_mode.value}, language_mode={subtitle_language_mode.value}): {output_path}")
            return output_path

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
            # Skip dropped segments
            if seg.state == SegmentState.DROP:
                continue
            start = _seconds_to_ass_time(seg.effective_start - time_offset)
            end = _seconds_to_ass_time(seg.effective_end - time_offset)

            # English subtitle - include if mode is BOTH or EN
            if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.EN):
                english_text = seg.en.replace("\n", "\\N")
                if english_text:
                    lines.append(f"Dialogue: 0,{start},{end},English,,0,0,0,,{english_text}")

            # Chinese subtitle - include if mode is BOTH or ZH
            if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.ZH):
                chinese_text = seg.zh.replace("\n", "\\N")
                if chinese_text:
                    if converter:
                        chinese_text = converter.convert(chinese_text)
                    lines.append(f"Dialogue: 0,{start},{end},Chinese,,0,0,0,,{chinese_text}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated ASS subtitle (style_mode={subtitle_style_mode.value}, language_mode={subtitle_language_mode.value}): {output_path}")
        return output_path

    async def export_full_video(
        self,
        timeline: Timeline,
        video_path: Path,
        output_path: Path,
        subtitle_style=None,
    ) -> Path:
        """Export full video with subtitles and pinned cards.

        Modes:
        - HALF_SCREEN (Learning): Video scaled to top, subtitles in bottom area
        - FLOATING (Watching): Transparent subtitles overlaid on full video
        - NONE (Dubbing): No subtitles

        Pinned cards appear on the right side with slide-in/fade-in animation.

        Args:
            timeline: Timeline with all segments
            video_path: Source video path
            output_path: Output video path
            subtitle_style: Optional subtitle style options

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
        subtitle_ratio = getattr(timeline, 'subtitle_area_ratio', 0.3)

        # Get subtitle style mode (default to HALF_SCREEN for backwards compatibility)
        subtitle_style_mode = getattr(timeline, 'subtitle_style_mode', SubtitleStyleMode.HALF_SCREEN)
        if subtitle_style_mode is None:
            subtitle_style_mode = SubtitleStyleMode.HALF_SCREEN

        # Get subtitle language mode (default to BOTH for backwards compatibility)
        subtitle_language_mode = getattr(timeline, 'subtitle_language_mode', SubtitleLanguageMode.BOTH)
        if subtitle_language_mode is None:
            subtitle_language_mode = SubtitleLanguageMode.BOTH

        # Filter segments: exclude dropped, apply trim range
        if trim_start > 0 or trim_end is not None:
            effective_trim_end = trim_end if trim_end is not None else float('inf')
            trimmed_segments = [
                seg for seg in timeline.segments
                if seg.state != SegmentState.DROP
                and seg.start >= trim_start and seg.end <= effective_trim_end
            ]
            time_offset = trim_start
        else:
            trimmed_segments = [
                seg for seg in timeline.segments
                if seg.state != SegmentState.DROP
            ]
            time_offset = 0.0

        # Render pinned cards (skip cards on dropped segments)
        dropped_seg_ids = {seg.id for seg in timeline.segments if seg.state == SegmentState.DROP}
        pinned_cards = [
            c for c in (getattr(timeline, 'pinned_cards', []) or [])
            if c.segment_id not in dropped_seg_ids
        ]
        cards_dir = output_path.parent / "cards"
        rendered_cards = await self.render_pinned_cards(
            pinned_cards=pinned_cards,
            output_dir=cards_dir,
            time_offset=time_offset,
        )

        # Generate ASS subtitle file based on mode
        ass_path = output_path.parent / "subtitles_full.ass"
        await self.generate_ass_with_layout(
            segments=trimmed_segments,
            output_path=ass_path,
            use_traditional=timeline.use_traditional_chinese,
            time_offset=time_offset,
            video_height=orig_height,
            subtitle_area_ratio=subtitle_ratio,
            subtitle_style=subtitle_style,
            subtitle_style_mode=subtitle_style_mode,
            subtitle_language_mode=subtitle_language_mode,
        )

        # Build ffmpeg command based on mode
        if subtitle_style_mode == SubtitleStyleMode.HALF_SCREEN:
            # Learning mode: Scale video to top portion, subtitles in bottom area
            vf_filter = self._build_half_screen_filter(
                orig_width, orig_height, subtitle_ratio, ass_path
            )
            mode_name = "half_screen (Learning)"
        elif subtitle_style_mode == SubtitleStyleMode.FLOATING:
            # Watching mode: Overlay transparent subtitles on full video
            vf_filter = self._build_floating_filter(ass_path)
            mode_name = "floating (Watching)"
        else:
            # None mode: No subtitles, just copy/re-encode video
            vf_filter = None
            mode_name = "none (Dubbing)"

        # Build ffmpeg command with trim support
        cmd = ["ffmpeg"]

        # Add seek option if trim start is set (faster when placed before -i)
        if trim_start > 0:
            cmd.extend(["-ss", str(trim_start)])

        cmd.extend(["-i", str(video_path)])

        # Add card inputs and overlay filter if we have pinned cards
        card_filter = ""
        card_inputs = []
        final_label = ""
        if rendered_cards:
            card_filter, card_inputs, final_label = self._build_card_overlay_filter(
                cards=rendered_cards,
                video_width=orig_width,
                video_height=orig_height,
            )
            cmd.extend(card_inputs)

        # Add duration limit if trim end is set
        if trim_end is not None:
            duration = trim_end - trim_start
            cmd.extend(["-t", str(duration)])

        # Build combined filter
        if card_filter and vf_filter:
            # Apply subtitle filter first, then card overlays
            # We need to chain them properly
            cmd.extend(["-filter_complex", f"{vf_filter}[subtitled];{card_filter.replace('[0:v]', '[subtitled]')}"])
            cmd.extend(["-map", f"[{final_label}]", "-map", "0:a?"])
        elif card_filter:
            cmd.extend(["-filter_complex", card_filter])
            cmd.extend(["-map", f"[{final_label}]", "-map", "0:a?"])
        elif vf_filter:
            cmd.extend(["-vf", vf_filter])

        if self.use_nvenc:
            cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "23"])

        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-y", str(output_path)])

        trim_info = ""
        if trim_start > 0 or trim_end is not None:
            trim_info = f", trim={trim_start:.1f}s-{trim_end or 'end'}"
        lang_info = f", lang={subtitle_language_mode.value}"
        cards_info = f", {len(rendered_cards)} cards" if rendered_cards else ""
        logger.info(f"Exporting full video with {mode_name} mode{lang_info}{trim_info}{cards_info}: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg export failed: {result.stderr}")

        logger.info(f"Full video exported: {output_path}")
        return output_path

    def _build_half_screen_filter(
        self,
        orig_width: int,
        orig_height: int,
        subtitle_ratio: float,
        ass_path: Path,
    ) -> str:
        """Build ffmpeg filter for half_screen mode (Learning).

        Layout:
        ┌─────────────────────┐
        │   Scaled Video      │  ← (1 - subtitle_ratio) of height
        │                     │
        ├─────────────────────┤
        │   English subtitle  │  ← subtitle_ratio of height
        │   中文字幕           │     (colored background)
        └─────────────────────┘
        """
        video_area_height = int(orig_height * (1 - subtitle_ratio))

        # Calculate scaled video dimensions while maintaining aspect ratio
        orig_aspect = orig_width / orig_height
        target_aspect = orig_width / video_area_height

        if orig_aspect >= target_aspect:
            scaled_width = orig_width
            scaled_height = int(orig_width / orig_aspect)
        else:
            scaled_height = video_area_height
            scaled_width = int(video_area_height * orig_aspect)

        logger.info(
            f"Half-screen layout: original={orig_width}x{orig_height}, "
            f"video_area={orig_width}x{video_area_height}, "
            f"scaled={scaled_width}x{scaled_height}"
        )

        # Escape ASS path for ffmpeg filter
        ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")

        # FFmpeg filter: scale → pad with background → overlay subtitles
        subtitle_bg_color = "0x1a2744"  # Dark blue matching review page
        return (
            f"scale={scaled_width}:{scaled_height},"
            f"pad={orig_width}:{orig_height}:(ow-iw)/2:0:{subtitle_bg_color},"
            f"setsar=1,"
            f"ass={ass_path_escaped}"
        )

    def _build_floating_filter(self, ass_path: Path) -> str:
        """Build ffmpeg filter for floating mode (Watching).

        Layout:
        ┌─────────────────────┐
        │                     │
        │   Full Video        │
        │                     │
        │   ─── Subtitles ─── │  ← Transparent overlay near bottom
        └─────────────────────┘
        """
        # Escape ASS path for ffmpeg filter
        ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")

        logger.info("Floating layout: subtitles overlay on full video")

        # Simple filter: just overlay ASS subtitles on video
        return f"ass={ass_path_escaped}"

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
        3. Generates re-timed ASS subtitles based on subtitle_style_mode
        4. Burns subtitles into final video

        Args:
            timeline: Timeline with segments (uses KEEP segments only)
            video_path: Source video path
            output_path: Output video path
            subtitle_style: Optional subtitle style options

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

        # Get subtitle style mode (default to HALF_SCREEN for backwards compatibility)
        subtitle_style_mode = getattr(timeline, 'subtitle_style_mode', SubtitleStyleMode.HALF_SCREEN)
        if subtitle_style_mode is None:
            subtitle_style_mode = SubtitleStyleMode.HALF_SCREEN

        # Get subtitle language mode (default to BOTH for backwards compatibility)
        subtitle_language_mode = getattr(timeline, 'subtitle_language_mode', SubtitleLanguageMode.BOTH)
        if subtitle_language_mode is None:
            subtitle_language_mode = SubtitleLanguageMode.BOTH

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

            # Get concatenated video dimensions for ASS header
            concat_width, concat_height = self._get_video_dimensions(concat_output)
            subtitle_ratio = getattr(timeline, 'subtitle_area_ratio', 0.3)

            # Generate re-timed ASS subtitles for essence based on mode
            retimed_segments = self._retime_segments(keep_segments)
            ass_path = output_path.parent / "subtitles_essence.ass"
            await self._generate_essence_ass(
                retimed_segments,
                ass_path,
                timeline.use_traditional_chinese,
                video_height=concat_height,
                subtitle_area_ratio=subtitle_ratio,
                subtitle_style=subtitle_style,
                subtitle_style_mode=subtitle_style_mode,
                subtitle_language_mode=subtitle_language_mode,
            )

            # Build ffmpeg filter based on mode
            if subtitle_style_mode == SubtitleStyleMode.HALF_SCREEN:
                vf_filter = self._build_half_screen_filter(
                    concat_width, concat_height, subtitle_ratio, ass_path
                )
                mode_name = "half_screen"
            elif subtitle_style_mode == SubtitleStyleMode.FLOATING:
                vf_filter = self._build_floating_filter(ass_path)
                mode_name = "floating"
            else:
                vf_filter = None
                mode_name = "none"

            cmd = ["ffmpeg", "-i", str(concat_output)]

            if vf_filter:
                cmd.extend(["-vf", vf_filter])

            if self.use_nvenc:
                cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4"])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "23"])

            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-y", str(output_path)])

            logger.info(f"Exporting essence video with {mode_name} mode, lang={subtitle_language_mode.value}: {output_path}")
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
        video_height: int = 1080,
        subtitle_area_ratio: float = 0.3,
        subtitle_style=None,
        subtitle_style_mode: SubtitleStyleMode = SubtitleStyleMode.HALF_SCREEN,
        subtitle_language_mode: SubtitleLanguageMode = SubtitleLanguageMode.BOTH,
    ) -> Path:
        """Generate ASS subtitles for retimed essence segments based on mode."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build SubtitleStyleConfig from request options
        config = SubtitleStyleConfig()
        if subtitle_style:
            config.en_font_size = getattr(subtitle_style, 'en_font_size', 40) or 40
            config.zh_font_size = getattr(subtitle_style, 'zh_font_size', 40) or 40
            config.en_color = getattr(subtitle_style, 'en_color', "#ffffff") or "#ffffff"
            config.zh_color = getattr(subtitle_style, 'zh_color', "#facc15") or "#facc15"
            config.background_color = getattr(subtitle_style, 'background_color', "#1a2744") or "#1a2744"

        # Generate ASS header based on mode
        style_mode = StyleMode(subtitle_style_mode.value)
        ass_header = generate_ass_header(
            mode=style_mode,
            video_height=video_height,
            subtitle_area_ratio=subtitle_area_ratio,
            config=config,
        )

        # If style mode is NONE or language mode is NONE, return empty ASS file
        if subtitle_style_mode == SubtitleStyleMode.NONE or subtitle_language_mode == SubtitleLanguageMode.NONE:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("")
            logger.info(f"Generated empty essence ASS subtitle (style_mode={subtitle_style_mode.value}, language_mode={subtitle_language_mode.value}): {output_path}")
            return output_path

        # Convert Simplified to Traditional if needed
        converter = None
        if use_traditional:
            try:
                import opencc
                converter = opencc.OpenCC("s2t")
            except ImportError:
                logger.warning("opencc not installed, using Simplified Chinese")

        lines = [ass_header]

        for start, end, en, zh in retimed_segments:
            start_str = _seconds_to_ass_time(start)
            end_str = _seconds_to_ass_time(end)

            # English subtitle - include if mode is BOTH or EN
            if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.EN):
                english_text = en.replace("\n", "\\N")
                if english_text:
                    lines.append(f"Dialogue: 0,{start_str},{end_str},English,,0,0,0,,{english_text}")

            # Chinese subtitle - include if mode is BOTH or ZH
            if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.ZH):
                chinese_text = zh.replace("\n", "\\N")
                if chinese_text:
                    if converter:
                        chinese_text = converter.convert(chinese_text)
                    lines.append(f"Dialogue: 0,{start_str},{end_str},Chinese,,0,0,0,,{chinese_text}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Generated essence ASS subtitle (style_mode={subtitle_style_mode.value}, language_mode={subtitle_language_mode.value}): {output_path}")
        return output_path
