"""Subtitle style templates for different rendering modes.

Three main styles:
- half_screen: Learning mode - video scaled to top, subtitles in dedicated bottom area
- floating: Watching mode - transparent subtitles overlaid on video
- none: Dubbing mode - no subtitles (or minimal)
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass


class SubtitleStyleMode(str, Enum):
    """Subtitle rendering style mode."""
    HALF_SCREEN = "half_screen"  # Learning: video on top, subtitles in bottom area
    FLOATING = "floating"  # Watching: transparent subtitles over video
    NONE = "none"  # Dubbing: no subtitles


@dataclass
class SubtitleStyleConfig:
    """Configuration for subtitle styling."""
    en_font_size: int = 40
    zh_font_size: int = 40
    en_color: str = "#ffffff"  # White
    zh_color: str = "#facc15"  # Yellow
    background_color: str = "#1a2744"  # Dark blue
    font_weight: str = "500"
    # Floating mode specific
    floating_position: str = "bottom"  # "top" or "bottom"
    floating_margin: int = 60  # Margin from edge in pixels


def _hex_to_ass_color(hex_color: str, opacity: int = 0) -> str:
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


def generate_half_screen_ass_header(
    video_height: int = 1080,
    subtitle_area_ratio: float = 0.5,
    config: Optional[SubtitleStyleConfig] = None,
) -> str:
    """Generate ASS header for half_screen mode (Learning).

    Layout:
    ┌─────────────────────┐
    │   Scaled Video      │  ← (1 - subtitle_area_ratio) of height
    │                     │
    ├─────────────────────┤
    │   English subtitle  │  ← subtitle_area_ratio of height
    │   中文字幕           │     (colored background)
    └─────────────────────┘

    Args:
        video_height: Total video height in pixels
        subtitle_area_ratio: Ratio of subtitle area (0.3-0.7)
        config: Subtitle style configuration

    Returns:
        ASS header string
    """
    config = config or SubtitleStyleConfig()

    # Calculate subtitle area dimensions
    subtitle_area_height = int(video_height * subtitle_area_ratio)

    # Scale font sizes based on subtitle area height
    # Base reference: 40px at 300px subtitle height
    scale_factor = subtitle_area_height / 300
    english_font_size = max(24, int(config.en_font_size * scale_factor))
    chinese_font_size = max(24, int(config.zh_font_size * scale_factor))

    # Calculate vertical positions to center both subtitles as a group
    gap_between = int(20 * scale_factor)
    total_block_height = english_font_size + gap_between + chinese_font_size
    block_bottom = (subtitle_area_height - total_block_height) // 2

    # Chinese at bottom, English above
    chinese_margin_v = max(10, block_bottom)
    english_margin_v = chinese_margin_v + chinese_font_size + gap_between

    # Swap to match frontend preview (English on top, Chinese on bottom)
    english_margin_v, chinese_margin_v = chinese_margin_v, english_margin_v

    # Convert colors
    english_color = _hex_to_ass_color(config.en_color, 0)
    chinese_color = _hex_to_ass_color(config.zh_color, 0)
    background_color = _hex_to_ass_color(config.background_color, 192)  # 75% opacity

    return f"""[Script Info]
Title: SceneMind Bilingual Subtitles - Learning Mode
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


def generate_floating_ass_header(
    video_height: int = 1080,
    config: Optional[SubtitleStyleConfig] = None,
) -> str:
    """Generate ASS header for floating mode (Watching).

    Subtitles are semi-transparent, floating over the video.
    Uses text shadow instead of opaque background.

    Layout:
    ┌─────────────────────┐
    │                     │
    │   Full Video        │
    │                     │
    │   ─── Subtitles ─── │  ← Near bottom/top, transparent BG
    └─────────────────────┘

    Args:
        video_height: Total video height in pixels
        config: Subtitle style configuration

    Returns:
        ASS header string
    """
    config = config or SubtitleStyleConfig()

    # Floating mode: slightly smaller fonts for less obstruction
    english_font_size = int(config.en_font_size * 0.9)  # 36px default
    chinese_font_size = int(config.zh_font_size * 0.9)  # 36px default

    # Colors for floating mode
    english_color = _hex_to_ass_color(config.en_color, 0)  # White
    chinese_color = _hex_to_ass_color(config.zh_color, 0)  # Yellow
    outline_color = _hex_to_ass_color("#000000", 0)  # Black outline
    shadow_color = _hex_to_ass_color("#000000", 128)  # Semi-transparent black shadow

    # Margin based on position
    margin_v = config.floating_margin
    if config.floating_position == "top":
        # For top position, use Alignment=8 (top center)
        alignment = 8
    else:
        # For bottom position, use Alignment=2 (bottom center)
        alignment = 2

    # Gap between English and Chinese
    # English above, Chinese below (for bottom alignment)
    english_margin_v = margin_v + chinese_font_size + 10
    chinese_margin_v = margin_v

    # BorderStyle=1: Outline + shadow (no background box)
    # Outline=3: Thick outline for readability
    # Shadow=2: Drop shadow for depth
    return f"""[Script Info]
Title: SceneMind Bilingual Subtitles - Watching Mode
ScriptType: v4.00+
PlayResX: 1920
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: English,Arial,{english_font_size},{english_color},&H000000FF,{outline_color},{shadow_color},0,0,0,0,100,100,0,0,1,3,2,{alignment},40,40,{english_margin_v},1
Style: Chinese,Microsoft YaHei,{chinese_font_size},{chinese_color},&H000000FF,{outline_color},{shadow_color},-1,0,0,0,100,100,0,0,1,3,2,{alignment},40,40,{chinese_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def generate_floating_single_line_ass_header(
    video_height: int = 1080,
    config: Optional[SubtitleStyleConfig] = None,
) -> str:
    """Generate ASS header for single-line floating mode.

    Both English and Chinese on same line, separated by " | ".
    More compact for minimal obstruction.

    Args:
        video_height: Total video height in pixels
        config: Subtitle style configuration

    Returns:
        ASS header string
    """
    config = config or SubtitleStyleConfig()

    # Combined font size (average of both)
    font_size = int((config.en_font_size + config.zh_font_size) / 2 * 0.85)

    # Use white for combined subtitle
    text_color = _hex_to_ass_color("#ffffff", 0)
    outline_color = _hex_to_ass_color("#000000", 0)
    shadow_color = _hex_to_ass_color("#000000", 128)

    margin_v = config.floating_margin
    alignment = 2 if config.floating_position == "bottom" else 8

    return f"""[Script Info]
Title: SceneMind Bilingual Subtitles - Watching Mode (Compact)
ScriptType: v4.00+
PlayResX: 1920
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Combined,Arial,{font_size},{text_color},&H000000FF,{outline_color},{shadow_color},0,0,0,0,100,100,0,0,1,3,2,{alignment},40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def generate_ass_header(
    mode: SubtitleStyleMode,
    video_height: int = 1080,
    subtitle_area_ratio: float = 0.5,
    config: Optional[SubtitleStyleConfig] = None,
) -> str:
    """Generate ASS header based on subtitle mode.

    Args:
        mode: Subtitle rendering mode
        video_height: Total video height in pixels
        subtitle_area_ratio: Ratio for half_screen mode
        config: Subtitle style configuration

    Returns:
        ASS header string
    """
    if mode == SubtitleStyleMode.HALF_SCREEN:
        return generate_half_screen_ass_header(video_height, subtitle_area_ratio, config)
    elif mode == SubtitleStyleMode.FLOATING:
        return generate_floating_ass_header(video_height, config)
    else:  # NONE
        return ""  # No subtitles


# Default ASS header for backwards compatibility (half_screen mode)
ASS_HEADER_DEFAULT = """[Script Info]
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
