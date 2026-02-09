"""Export worker for video rendering with bilingual subtitles."""

import asyncio
import hashlib
import json
import math
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple
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

# WYSIWYG export constants (matches UI 65/35 split)
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080
VIDEO_AREA_RATIO = 0.65  # Left 65% for video
CARD_PANEL_RATIO = 0.35  # Right 35% for card panel
PANEL_BG_COLOR = "0x1a2744"


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

    async def render_pinned_cards_full_panel(
        self,
        pinned_cards: List[PinnedCard],
        output_dir: Path,
        panel_width: int,
        panel_height: int,
        time_offset: float = 0.0,
    ) -> List[Tuple[Path, float, float]]:
        """Render pinned cards as full-detail panel images for WYSIWYG export.

        Args:
            pinned_cards: List of pinned cards
            output_dir: Directory to save card images
            panel_width: Width of the right panel area
            panel_height: Height of the panel area (video area height)
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

            card_path = output_dir / f"panel_card_{i:03d}_{card.id}.png"
            try:
                card_type = card.card_type.value if hasattr(card.card_type, 'value') else card.card_type
                renderer.render_full_panel_card(
                    card_data=card.card_data,
                    card_type=card_type,
                    panel_width=panel_width,
                    panel_height=panel_height,
                    output_path=card_path,
                )

                display_start = max(0, card.display_start - time_offset)
                display_end = max(0, card.display_end - time_offset)

                if display_end > display_start:
                    rendered_cards.append((card_path, display_start, display_end))
                    logger.debug(
                        f"Rendered full panel card {card.id} ({card_type}): "
                        f"{display_start:.1f}s - {display_end:.1f}s"
                    )
            except Exception as e:
                logger.error(f"Failed to render full panel card {card.id}: {e}")

        logger.info(f"Rendered {len(rendered_cards)} full panel cards ({panel_width}x{panel_height})")
        return rendered_cards

    def _build_wysiwyg_filter(
        self,
        cards: List[Tuple[Path, float, float]],
        video_duration: float,
        subtitle_ratio: float,
        ass_path: Path,
    ) -> Tuple[str, List[str], str]:
        """Build FFmpeg filter_complex for WYSIWYG 65/35 side-by-side layout.

        Layout:
        +---- Left 1248px (65%) ----+--- Right 672px (35%) ---+
        |  Video (scaled, centered,  |  Full Card Detail Panel  |
        |  padded with #1a2744)      |  bg: #1a2744             |
        |  Height: 756px             |  Height: 756px           |
        +----------------------------+--------------------------+
        | Subtitle Area (1920px full width, bg: #1a2744)        |
        | Height: 324px                                         |
        +-------------------------------------------------------+

        Args:
            cards: List of (image_path, start_time, end_time) tuples
            video_duration: Total video duration for canvas
            subtitle_ratio: Subtitle area ratio (e.g. 0.3)
            ass_path: Path to ASS subtitle file

        Returns:
            Tuple of (filter_complex string, input arguments, final output label)
        """
        left_width = int(OUTPUT_WIDTH * VIDEO_AREA_RATIO)  # 1248
        right_width = OUTPUT_WIDTH - left_width  # 672
        video_area_height = int(OUTPUT_HEIGHT * (1 - subtitle_ratio))  # 756

        # Escape ASS path for ffmpeg filter
        ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")

        input_args = []
        filters = []

        # Step 1: Create background canvas (dark blue, full output size)
        filters.append(
            f"color=c={PANEL_BG_COLOR}:s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}"
            f":d={video_duration}:r=30[canvas]"
        )

        # Step 2: Scale source video to fit left panel area
        # Left panel is left_width x video_area_height
        filters.append(
            f"[0:v]scale={left_width}:{video_area_height}"
            f":force_original_aspect_ratio=decrease[scaled_v]"
        )

        # Step 3: Overlay scaled video centered in left panel area
        # Center: x = (left_width - overlay_w) / 2, y = (video_area_height - overlay_h) / 2
        filters.append(
            f"[canvas][scaled_v]overlay="
            f"x='({left_width}-overlay_w)/2':y='({video_area_height}-overlay_h)/2'"
            f"[with_video]"
        )

        # Step 4: Overlay card PNGs in right panel area with animation
        prev_label = "with_video"
        for i, (card_path, start, end) in enumerate(cards):
            input_idx = i + 1  # 0 is the source video
            input_args.extend(["-i", str(card_path)])

            # Animation parameters
            fade_in_duration = CARD_ANIMATION_DURATION
            slide_distance = 24  # Subtle slide matching React animation

            t_start = start
            t_fade_in_end = start + fade_in_duration
            t_end = end

            # Full panel cards fill the right panel area exactly
            card_x = left_width
            card_y = 0

            # X position expression: slide in from right (24px offset)
            x_expr = (
                f"if(lt(t,{t_start}),{left_width}+{right_width},"
                f"if(lt(t,{t_fade_in_end}),"
                f"{card_x}+{slide_distance}*(1-(t-{t_start})/{fade_in_duration}),"
                f"{card_x}))"
            )

            enable_expr = f"between(t,{t_start},{t_end})"

            out_label = f"card{i}"
            filters.append(
                f"[{prev_label}][{input_idx}:v]overlay="
                f"x='{x_expr}':y='{card_y}':"
                f"enable='{enable_expr}':"
                f"format=auto"
                f"[{out_label}]"
            )
            prev_label = out_label

        # Step 5: Draw subtle divider lines between areas
        # Vertical divider: between video (left) and card panel (right)
        # Horizontal divider: between video+card area and subtitle area
        # FFmpeg hex color: 0xRRGGBB@opacity (white at 10%)
        filters.append(
            f"[{prev_label}]drawbox="
            f"x={left_width}:y=0:w=1:h={video_area_height}:"
            f"color=0xFFFFFF@0.1:t=fill"
            f"[div1]"
        )
        filters.append(
            f"[div1]drawbox="
            f"x=0:y={video_area_height}:w={OUTPUT_WIDTH}:h=1:"
            f"color=0xFFFFFF@0.1:t=fill"
            f"[with_dividers]"
        )

        # Step 6: Burn subtitles (spans full 1920px width)
        final_label = "final_out"
        filters.append(
            f"[with_dividers]ass={ass_path_escaped}[{final_label}]"
        )

        filter_complex = ";".join(filters)

        logger.info(
            f"WYSIWYG filter: {left_width}x{video_area_height} video + "
            f"{right_width}x{video_area_height} card panel, "
            f"{len(cards)} cards, subtitles at bottom"
        )

        return filter_complex, input_args, final_label

    def _retime_pinned_cards(
        self,
        pinned_cards: List[PinnedCard],
        keep_segments: List[EditableSegment],
    ) -> List[PinnedCard]:
        """Retime pinned cards to match concatenated KEEP-segment video.

        Uses the same cumulative-offset approach as _retime_segments().

        Args:
            pinned_cards: Original pinned cards
            keep_segments: KEEP segments in order

        Returns:
            New PinnedCard list with adjusted display_start/display_end
        """
        # Build time mapping: original time -> retimed time
        # Each keep segment maps to a contiguous block in the output
        retimed_cards = []
        cumulative_time = 0.0

        # Build segment time ranges
        segment_offsets = []
        for seg in keep_segments:
            seg_start = seg.effective_start
            seg_end = seg.effective_end
            seg_duration = seg.effective_duration
            # offset = retimed_start - original_start
            offset = cumulative_time - seg_start
            segment_offsets.append((seg_start, seg_end, offset))
            cumulative_time += seg_duration

        for card in pinned_cards:
            if not card.card_data:
                continue

            # Find which segment this card belongs to
            new_start = None
            new_end = None
            for seg_start, seg_end, offset in segment_offsets:
                # Card display window overlaps with this segment
                if card.display_start < seg_end and card.display_end > seg_start:
                    # Clamp card timing to segment boundaries, then apply offset
                    clamped_start = max(card.display_start, seg_start)
                    clamped_end = min(card.display_end, seg_end)
                    new_start = clamped_start + offset
                    new_end = clamped_end + offset
                    break

            if new_start is not None and new_end is not None and new_end > new_start:
                # Create a copy with new timing
                retimed_card = card.model_copy(
                    update={"display_start": new_start, "display_end": new_end}
                )
                retimed_cards.append(retimed_card)

        logger.info(f"Retimed {len(retimed_cards)}/{len(pinned_cards)} pinned cards for essence export")
        return retimed_cards

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

    def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration in seconds using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "csv=s=x:p=0",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning(f"ffprobe duration failed: {result.stderr}")
            return 0.0
        try:
            return float(result.stdout.strip())
        except (ValueError, TypeError):
            return 0.0

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

    def _replace_image_urls_with_local(self, card_data: dict, card_type: str) -> dict:
        """Replace remote image URLs in card_data with local cached file:// paths.

        Remotion's browser can load file:// URLs during server-side render.
        Images must already be pre-cached via batch_precache_images().
        URLs without a local cache (e.g. expired Pixabay links) are removed
        so the card renders gracefully without the image.
        """
        from app.workers.card_renderer import IMAGE_CACHE_DIR

        data = dict(card_data)  # shallow copy
        if card_type == "entity" and data.get("image_url"):
            url = data["image_url"]
            url_hash = hashlib.md5(url.encode()).hexdigest()
            local_path = IMAGE_CACHE_DIR / f"{url_hash}.png"
            if local_path.exists():
                data["image_url"] = local_path.resolve().as_uri()
            else:
                logger.warning(f"Image not cached, removing expired URL: {url[:80]}...")
                data["image_url"] = None
        elif card_type == "word" and data.get("images"):
            new_images = []
            for url in data["images"]:
                url_hash = hashlib.md5(url.encode()).hexdigest()
                local_path = IMAGE_CACHE_DIR / f"{url_hash}.png"
                if local_path.exists():
                    new_images.append(local_path.resolve().as_uri())
                else:
                    logger.warning(f"Image not cached, skipping expired URL: {url[:80]}...")
            data["images"] = new_images
        return data

    async def _render_with_remotion(
        self,
        segments: List[EditableSegment],
        pinned_cards: List[PinnedCard],
        video_path: Path,
        output_path: Path,
        video_duration: float,
        subtitle_style=None,
        time_offset: float = 0.0,
        retimed_segments: Optional[List[Tuple[float, float, str, str]]] = None,
        use_traditional: bool = True,
        subtitle_language_mode: SubtitleLanguageMode = SubtitleLanguageMode.BOTH,
        subtitle_area_ratio: float = 0.3,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Path:
        """Render video using Remotion LearningVideo composition.

        This produces pixel-perfect WYSIWYG output by rendering the actual
        React card components from CardSidePanel.tsx in a headless browser.

        Args:
            segments: Editable segments (used if retimed_segments is None)
            pinned_cards: Pinned cards with card_data
            video_path: Path to source video
            output_path: Path for output video
            video_duration: Duration in seconds
            subtitle_style: Optional subtitle style options
            time_offset: Time offset for segment timing
            retimed_segments: Pre-retimed (start, end, en, zh) tuples for essence
            use_traditional: Convert to Traditional Chinese
            subtitle_language_mode: Which subtitles to include
            subtitle_area_ratio: Ratio for subtitle area height

        Returns:
            Path to rendered video
        """
        fps = 30
        duration_in_frames = math.ceil(video_duration * fps)

        # Pre-cache all card images
        from app.workers.card_renderer import batch_precache_images
        card_dicts = [
            {"card_type": c.card_type.value if hasattr(c.card_type, 'value') else c.card_type,
             "card_data": c.card_data}
            for c in pinned_cards if c.card_data
        ]
        batch_precache_images(card_dicts)

        # Convert Simplified to Traditional if needed
        converter = None
        if use_traditional:
            try:
                import opencc
                converter = opencc.OpenCC("s2t")
            except ImportError:
                logger.warning("opencc not installed, using Simplified Chinese")

        # Build pinned card props with local image paths
        pinned_card_props = []
        for card in pinned_cards:
            if not card.card_data:
                continue
            card_type = card.card_type.value if hasattr(card.card_type, 'value') else card.card_type
            card_data = self._replace_image_urls_with_local(card.card_data, card_type)

            display_start = max(0, card.display_start - time_offset)
            display_end = max(0, card.display_end - time_offset)
            if display_end <= display_start:
                continue

            pinned_card_props.append({
                "id": card.id,
                "card_type": card_type,
                "card_data": card_data,
                "display_start": display_start,
                "display_end": display_end,
            })

        # Build subtitle props
        subtitle_props = []
        if subtitle_language_mode != SubtitleLanguageMode.NONE:
            if retimed_segments is not None:
                # Essence mode: use pre-retimed segments
                for i, (start, end, en, zh) in enumerate(retimed_segments):
                    sub_en = en if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.EN) else ""
                    sub_zh = zh if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.ZH) else ""
                    if converter and sub_zh:
                        sub_zh = converter.convert(sub_zh)
                    if sub_en or sub_zh:
                        subtitle_props.append({
                            "id": i,
                            "start": start,
                            "end": end,
                            "en": sub_en,
                            "zh": sub_zh,
                        })
            else:
                # Full video mode: use segments with offset
                for seg in segments:
                    if seg.state == SegmentState.DROP:
                        continue
                    sub_en = seg.en if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.EN) else ""
                    sub_zh = seg.zh if subtitle_language_mode in (SubtitleLanguageMode.BOTH, SubtitleLanguageMode.ZH) else ""
                    if converter and sub_zh:
                        sub_zh = converter.convert(sub_zh)
                    if sub_en or sub_zh:
                        subtitle_props.append({
                            "id": seg.id,
                            "start": seg.effective_start - time_offset,
                            "end": seg.effective_end - time_offset,
                            "en": sub_en,
                            "zh": sub_zh,
                        })

        # Build subtitle style
        en_font_size = 40
        zh_font_size = 40
        en_color = "#ffffff"
        zh_color = "#facc15"
        bg_color = "#1a2744"
        if subtitle_style:
            en_font_size = getattr(subtitle_style, 'en_font_size', 40) or 40
            zh_font_size = getattr(subtitle_style, 'zh_font_size', 40) or 40
            en_color = getattr(subtitle_style, 'en_color', "#ffffff") or "#ffffff"
            zh_color = getattr(subtitle_style, 'zh_color', "#facc15") or "#facc15"
            bg_color = getattr(subtitle_style, 'background_color', "#1a2744") or "#1a2744"

        # Build Remotion input props
        input_props = {
            "videoSrc": str(video_path.resolve()),
            "durationInFrames": duration_in_frames,
            "fps": fps,
            "width": OUTPUT_WIDTH,
            "height": OUTPUT_HEIGHT,
            "pinnedCards": pinned_card_props,
            "subtitles": subtitle_props,
            "layout": {
                "videoRatio": VIDEO_AREA_RATIO,
                "subtitleRatio": subtitle_area_ratio,
                "bgColor": bg_color,
            },
            "subtitleStyle": {
                "enColor": en_color,
                "zhColor": zh_color,
                "enFontSize": en_font_size,
                "zhFontSize": zh_font_size,
            },
        }

        # Write props to temp JSON file
        props_file = output_path.parent / "remotion_props.json"
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump(input_props, f, ensure_ascii=False)

        # Find the render script via settings.frontend_dir
        frontend_dir = settings.frontend_dir.resolve()
        render_script = frontend_dir / "remotion" / "render.mjs"
        if not render_script.exists():
            raise RuntimeError(
                f"Remotion render script not found: {render_script}. "
                f"Set FRONTEND_DIR env var to the frontend directory path."
            )

        # Ensure node_modules exist (auto-install on first run in Docker)
        node_modules = frontend_dir / "node_modules"
        if not node_modules.exists():
            logger.info("node_modules not found, running pnpm install...")
            install_result = subprocess.run(
                ["pnpm", "install", "--frozen-lockfile"],
                capture_output=True, text=True,
                cwd=str(frontend_dir),
                timeout=300,
            )
            if install_result.returncode != 0:
                raise RuntimeError(
                    f"pnpm install failed: {install_result.stderr[-500:]}"
                )
            logger.info("pnpm install completed")

        # Run Remotion render (async subprocess with streaming progress)
        cmd = [
            "node", str(render_script),
            "--input", str(props_file),
            "--output", str(output_path),
            "--composition", "LearningVideo",
        ]

        logger.info(
            f"Remotion render: {len(pinned_card_props)} cards, "
            f"{len(subtitle_props)} subtitles, "
            f"{duration_in_frames} frames @ {fps}fps"
        )

        # Timeout: ~0.5s per frame at moderate concurrency, minimum 10 min
        timeout_seconds = max(600, int(duration_in_frames * 0.5))
        logger.info(f"Remotion timeout set to {timeout_seconds}s ({timeout_seconds // 60} min)")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(frontend_dir),
        )

        # Stream stdout line-by-line for real-time progress + ETA
        last_progress = 0
        render_start_time = time.monotonic()
        stderr_lines: list[str] = []
        try:
            async def read_stderr():
                assert proc.stderr is not None
                async for raw in proc.stderr:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if line:
                        stderr_lines.append(line)

            stderr_task = asyncio.create_task(read_stderr())

            assert proc.stdout is not None
            async for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if msg.get("type") == "progress":
                        progress = msg.get("progress", 0)
                        if progress > last_progress:
                            last_progress = progress
                            # Calculate ETA
                            elapsed = time.monotonic() - render_start_time
                            eta_str = ""
                            if progress > 5 and elapsed > 3:
                                remaining = elapsed / (progress / 100) * (1 - progress / 100)
                                if remaining > 3600:
                                    eta_str = f"{remaining / 3600:.1f}h"
                                elif remaining > 60:
                                    eta_str = f"{int(remaining // 60)}m{int(remaining % 60):02d}s"
                                else:
                                    eta_str = f"{int(remaining)}s"
                            status_msg = msg.get('status', '')
                            log_msg = f"Remotion render: {progress}%"
                            if eta_str:
                                log_msg += f" · ETA {eta_str}"
                            logger.info(log_msg)
                            # Report to caller for UI update
                            if progress_callback and progress > 10:
                                # Map Remotion 10-100% to export 10-65%
                                export_progress = 10 + (progress - 10) * 55 / 90
                                cb_msg = f"渲染中"
                                if eta_str:
                                    cb_msg += f" · 预计剩余 {eta_str}"
                                progress_callback(export_progress, cb_msg)
                    elif msg.get("type") == "complete":
                        logger.info(f"Remotion render complete: {msg.get('outputPath')}")
                except (json.JSONDecodeError, TypeError):
                    logger.debug(f"Remotion stdout: {line[:200]}")

            await asyncio.wait_for(proc.wait(), timeout=timeout_seconds)
            await stderr_task

        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(
                f"Remotion render timed out after {timeout_seconds}s "
                f"({duration_in_frames} frames). Last progress: {last_progress}%"
            )

        if proc.returncode != 0:
            stderr_text = "\n".join(stderr_lines[-20:])
            raise RuntimeError(f"Remotion render failed (exit {proc.returncode}): {stderr_text[-1000:]}")

        logger.info(f"Remotion WYSIWYG video exported: {output_path}")
        return output_path

    async def export_full_video(
        self,
        timeline: Timeline,
        video_path: Path,
        output_path: Path,
        subtitle_style=None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
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

        # WYSIWYG mode: HALF_SCREEN uses Remotion for pixel-perfect React rendering
        if subtitle_style_mode == SubtitleStyleMode.HALF_SCREEN:
            # Get video duration
            video_duration = self._get_video_duration(video_path)
            if trim_end is not None:
                video_duration = min(video_duration, trim_end - trim_start)

            # Determine source video: trim if needed
            if trim_start > 0 or trim_end is not None:
                trimmed_video = output_path.parent / "trimmed_source.mp4"
                trim_cmd = ["ffmpeg", "-ss", str(trim_start), "-i", str(video_path)]
                if trim_end is not None:
                    trim_cmd.extend(["-t", str(trim_end - trim_start)])
                trim_cmd.extend(["-c", "copy", "-y", str(trimmed_video)])
                trim_result = subprocess.run(trim_cmd, capture_output=True, text=True)
                if trim_result.returncode != 0:
                    raise RuntimeError(f"ffmpeg trim failed: {trim_result.stderr}")
                source_video = trimmed_video
            else:
                source_video = video_path

            return await self._render_with_remotion(
                segments=trimmed_segments,
                pinned_cards=pinned_cards,
                video_path=source_video,
                output_path=output_path,
                video_duration=video_duration,
                subtitle_style=subtitle_style,
                time_offset=time_offset,
                use_traditional=timeline.use_traditional_chinese,
                subtitle_language_mode=subtitle_language_mode,
                subtitle_area_ratio=subtitle_ratio,
                progress_callback=progress_callback,
            )
        else:
            # FLOATING / NONE modes: existing behavior (full-width video)
            rendered_cards = await self.render_pinned_cards(
                pinned_cards=pinned_cards,
                output_dir=cards_dir,
                time_offset=time_offset,
            )

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

            if subtitle_style_mode == SubtitleStyleMode.FLOATING:
                vf_filter = self._build_floating_filter(ass_path)
                mode_name = "floating (Watching)"
            else:
                vf_filter = None
                mode_name = "none (Dubbing)"

            cmd = ["ffmpeg"]
            if trim_start > 0:
                cmd.extend(["-ss", str(trim_start)])
            cmd.extend(["-i", str(video_path)])

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

            if trim_end is not None:
                cmd.extend(["-t", str(trim_end - trim_start)])

            if card_filter and vf_filter:
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

            cards_info = f", {len(rendered_cards)} cards" if rendered_cards else ""

        trim_info = ""
        if trim_start > 0 or trim_end is not None:
            trim_info = f", trim={trim_start:.1f}s-{trim_end or 'end'}"
        lang_info = f", lang={subtitle_language_mode.value}"
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
        progress_callback: Optional[Callable[[float, str], None]] = None,
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

            # WYSIWYG mode: HALF_SCREEN uses Remotion for pixel-perfect rendering
            if subtitle_style_mode == SubtitleStyleMode.HALF_SCREEN:
                # Retime pinned cards to match concatenated segments
                dropped_seg_ids = {seg.id for seg in timeline.segments if seg.state == SegmentState.DROP}
                pinned_cards = [
                    c for c in (getattr(timeline, 'pinned_cards', []) or [])
                    if c.segment_id not in dropped_seg_ids
                ]
                retimed_pinned = self._retime_pinned_cards(pinned_cards, keep_segments)

                concat_duration = self._get_video_duration(concat_output)

                result_path = await self._render_with_remotion(
                    segments=[],  # not used when retimed_segments is provided
                    pinned_cards=retimed_pinned,
                    video_path=concat_output,
                    output_path=output_path,
                    video_duration=concat_duration,
                    subtitle_style=subtitle_style,
                    retimed_segments=retimed_segments,
                    use_traditional=timeline.use_traditional_chinese,
                    subtitle_language_mode=subtitle_language_mode,
                    subtitle_area_ratio=subtitle_ratio,
                    progress_callback=progress_callback,
                )

                logger.info(
                    f"Essence video exported: {output_path} "
                    f"({len(keep_segments)} segments, {timeline.keep_duration:.1f}s)"
                )
                return result_path
            else:
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

                if subtitle_style_mode == SubtitleStyleMode.FLOATING:
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
        progress_callback: Optional[Callable[[float, str], None]] = None,
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
            await self.export_full_video(timeline, video_path, full_path, subtitle_style, progress_callback)

        if profile in (ExportProfile.ESSENCE, ExportProfile.BOTH):
            essence_path = output_dir / "essence.mp4"
            await self.export_essence(timeline, video_path, essence_path, subtitle_style, progress_callback)

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
