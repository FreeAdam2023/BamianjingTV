"""Tests for subtitle styles worker."""

import pytest

from app.workers.subtitle_styles import (
    SubtitleStyleMode,
    SubtitleStyleConfig,
    _hex_to_ass_color,
    generate_half_screen_ass_header,
    generate_floating_ass_header,
    generate_floating_single_line_ass_header,
    generate_ass_header,
)


class TestHexToAssColor:
    """Tests for hex to ASS color conversion."""

    def test_white_color(self):
        """Test converting white color."""
        result = _hex_to_ass_color("#ffffff")
        assert result == "&H00FFFFFF"

    def test_black_color(self):
        """Test converting black color."""
        result = _hex_to_ass_color("#000000")
        assert result == "&H00000000"

    def test_yellow_color(self):
        """Test converting yellow color (used for Chinese subtitles)."""
        result = _hex_to_ass_color("#facc15")
        # ASS format is AABBGGRR (reversed RGB)
        # #facc15 -> R=fa, G=cc, B=15 -> &H0015CCFA
        assert result == "&H0015CCFA"

    def test_with_opacity(self):
        """Test color with opacity."""
        result = _hex_to_ass_color("#ffffff", opacity=128)
        assert result == "&H80FFFFFF"

    def test_without_hash(self):
        """Test color without # prefix."""
        result = _hex_to_ass_color("ffffff")
        assert result == "&H00FFFFFF"

    def test_invalid_color_returns_default(self):
        """Test that invalid color returns default white."""
        result = _hex_to_ass_color("#fff")  # Too short
        assert result == "&H00FFFFFF"


class TestGenerateHalfScreenAssHeader:
    """Tests for half-screen ASS header generation."""

    def test_default_generation(self):
        """Test default header generation."""
        header = generate_half_screen_ass_header()

        assert "[Script Info]" in header
        assert "PlayResY: 1080" in header
        assert "[V4+ Styles]" in header
        assert "Style: English" in header
        assert "Style: Chinese" in header
        assert "[Events]" in header

    def test_custom_video_height(self):
        """Test with custom video height."""
        header = generate_half_screen_ass_header(video_height=720)
        assert "PlayResY: 720" in header

    def test_custom_subtitle_ratio(self):
        """Test with custom subtitle area ratio."""
        header = generate_half_screen_ass_header(subtitle_area_ratio=0.3)
        # Should still generate valid header
        assert "[Script Info]" in header

    def test_custom_config(self):
        """Test with custom style configuration."""
        config = SubtitleStyleConfig(
            en_font_size=50,
            zh_font_size=60,
            en_color="#ff0000",
            zh_color="#00ff00",
        )
        header = generate_half_screen_ass_header(config=config)
        assert "[Script Info]" in header


class TestGenerateFloatingAssHeader:
    """Tests for floating ASS header generation."""

    def test_default_generation(self):
        """Test default floating header generation."""
        header = generate_floating_ass_header()

        assert "[Script Info]" in header
        assert "Watching Mode" in header
        assert "Style: English" in header
        assert "Style: Chinese" in header

    def test_top_position(self):
        """Test floating subtitles at top."""
        config = SubtitleStyleConfig(floating_position="top")
        header = generate_floating_ass_header(config=config)
        # Alignment 8 is top center
        assert ",8," in header

    def test_bottom_position(self):
        """Test floating subtitles at bottom."""
        config = SubtitleStyleConfig(floating_position="bottom")
        header = generate_floating_ass_header(config=config)
        # Alignment 2 is bottom center
        assert ",2," in header


class TestGenerateFloatingSingleLineAssHeader:
    """Tests for single-line floating ASS header."""

    def test_default_generation(self):
        """Test default single-line header."""
        header = generate_floating_single_line_ass_header()

        assert "[Script Info]" in header
        assert "Compact" in header
        assert "Style: Combined" in header

    def test_custom_config(self):
        """Test with custom config."""
        config = SubtitleStyleConfig(floating_margin=100)
        header = generate_floating_single_line_ass_header(config=config)
        assert "[Script Info]" in header


class TestGenerateAssHeader:
    """Tests for the main ASS header generation function."""

    def test_half_screen_mode(self):
        """Test half-screen mode dispatch."""
        header = generate_ass_header(SubtitleStyleMode.HALF_SCREEN)
        assert "Learning Mode" in header

    def test_floating_mode(self):
        """Test floating mode dispatch."""
        header = generate_ass_header(SubtitleStyleMode.FLOATING)
        assert "Watching Mode" in header

    def test_none_mode(self):
        """Test none mode returns empty string."""
        header = generate_ass_header(SubtitleStyleMode.NONE)
        assert header == ""

    def test_with_custom_parameters(self):
        """Test with all custom parameters."""
        config = SubtitleStyleConfig(en_font_size=48, zh_font_size=56)
        header = generate_ass_header(
            mode=SubtitleStyleMode.HALF_SCREEN,
            video_height=720,
            subtitle_area_ratio=0.4,
            config=config,
        )
        assert "PlayResY: 720" in header


class TestSubtitleStyleConfig:
    """Tests for SubtitleStyleConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SubtitleStyleConfig()

        assert config.en_font_size == 40
        assert config.zh_font_size == 40
        assert config.en_color == "#ffffff"
        assert config.zh_color == "#facc15"
        assert config.background_color == "#1a2744"
        assert config.floating_position == "bottom"
        assert config.floating_margin == 60

    def test_custom_values(self):
        """Test custom configuration values."""
        config = SubtitleStyleConfig(
            en_font_size=50,
            zh_font_size=60,
            en_color="#ff0000",
        )

        assert config.en_font_size == 50
        assert config.zh_font_size == 60
        assert config.en_color == "#ff0000"
