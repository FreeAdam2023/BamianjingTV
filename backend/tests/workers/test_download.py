"""Tests for download worker, especially VTT parsing."""

import pytest
import tempfile
from pathlib import Path

from app.workers.download import DownloadWorker


class TestVTTParsing:
    """Tests for YouTube VTT subtitle parsing."""

    @pytest.fixture
    def worker(self):
        return DownloadWorker()

    @pytest.mark.asyncio
    async def test_parse_standard_vtt(self, worker, tmp_path):
        """Test parsing standard VTT format with HH:MM:SS.mmm timestamps."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
Hello, welcome to the show.

00:00:05.500 --> 00:00:10.000
Today we're talking about AI.

00:00:10.500 --> 00:00:15.000
It's a fascinating topic.
"""
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(vtt_content)

        segments = await worker.parse_youtube_subtitles(vtt_file)

        assert len(segments) == 3
        assert segments[0]["text"] == "Hello, welcome to the show."
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 5.0
        assert segments[1]["text"] == "Today we're talking about AI."
        assert segments[2]["text"] == "It's a fascinating topic."

    @pytest.mark.asyncio
    async def test_parse_short_timestamp_vtt(self, worker, tmp_path):
        """Test parsing VTT with MM:SS.mmm timestamps (no hours)."""
        vtt_content = """WEBVTT

00:00.000 --> 00:05.000
First segment without hours.

00:05.500 --> 00:10.000
Second segment.
"""
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(vtt_content)

        segments = await worker.parse_youtube_subtitles(vtt_file)

        assert len(segments) == 2
        assert segments[0]["text"] == "First segment without hours."
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 5.0

    @pytest.mark.asyncio
    async def test_parse_vtt_with_positioning(self, worker, tmp_path):
        """Test parsing VTT with positioning/styling after timestamp."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000 align:start position:0%
Hello with positioning.

00:00:05.500 --> 00:00:10.000 line:90%
Second with line position.
"""
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(vtt_content)

        segments = await worker.parse_youtube_subtitles(vtt_file)

        assert len(segments) == 2
        assert segments[0]["text"] == "Hello with positioning."
        assert segments[1]["text"] == "Second with line position."

    @pytest.mark.asyncio
    async def test_parse_vtt_with_html_tags(self, worker, tmp_path):
        """Test that HTML/VTT tags are removed from text."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
<c.colorCCCCCC>This has</c> <b>formatting</b> tags.

00:00:05.500 --> 00:00:10.000
<v Speaker>Named voice span.</v>
"""
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(vtt_content)

        segments = await worker.parse_youtube_subtitles(vtt_file)

        assert len(segments) == 2
        assert segments[0]["text"] == "This has formatting tags."
        assert segments[1]["text"] == "Named voice span."

    @pytest.mark.asyncio
    async def test_parse_vtt_with_cue_identifiers(self, worker, tmp_path):
        """Test parsing VTT with numeric cue identifiers."""
        vtt_content = """WEBVTT

1
00:00:00.000 --> 00:00:05.000
First cue with identifier.

2
00:00:05.500 --> 00:00:10.000
Second cue.
"""
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(vtt_content)

        segments = await worker.parse_youtube_subtitles(vtt_file)

        assert len(segments) == 2
        assert segments[0]["text"] == "First cue with identifier."

    @pytest.mark.asyncio
    async def test_merge_duplicate_segments(self, worker, tmp_path):
        """Test that consecutive segments with same text are merged."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:02.000
Same text here.

00:00:02.000 --> 00:00:04.000
Same text here.

00:00:04.000 --> 00:00:06.000
Different text.
"""
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(vtt_content)

        segments = await worker.parse_youtube_subtitles(vtt_file)

        assert len(segments) == 2
        assert segments[0]["text"] == "Same text here."
        assert segments[0]["start"] == 0.0
        assert segments[0]["end"] == 4.0  # Extended to cover both
        assert segments[1]["text"] == "Different text."

    @pytest.mark.asyncio
    async def test_parse_multiline_text(self, worker, tmp_path):
        """Test parsing VTT with multi-line subtitle text."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
This is the first line.
And this is the second line.

00:00:05.500 --> 00:00:10.000
Single line here.
"""
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(vtt_content)

        segments = await worker.parse_youtube_subtitles(vtt_file)

        assert len(segments) == 2
        assert segments[0]["text"] == "This is the first line. And this is the second line."

    @pytest.mark.asyncio
    async def test_parse_empty_vtt(self, worker, tmp_path):
        """Test parsing empty VTT file."""
        vtt_content = """WEBVTT

"""
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(vtt_content)

        segments = await worker.parse_youtube_subtitles(vtt_file)

        assert len(segments) == 0

    @pytest.mark.asyncio
    async def test_speaker_field_set(self, worker, tmp_path):
        """Test that speaker field is set to default value."""
        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:05.000
Test segment.
"""
        vtt_file = tmp_path / "test.vtt"
        vtt_file.write_text(vtt_content)

        segments = await worker.parse_youtube_subtitles(vtt_file)

        assert len(segments) == 1
        assert segments[0]["speaker"] == "SPEAKER_00"


class TestVTTTimestampParsing:
    """Tests for VTT timestamp parsing helper."""

    @pytest.fixture
    def worker(self):
        return DownloadWorker()

    def test_parse_full_timestamp(self, worker):
        """Test parsing HH:MM:SS.mmm format."""
        result = worker._parse_vtt_timestamp("01:23:45.678")
        expected = 1 * 3600 + 23 * 60 + 45.678
        assert abs(result - expected) < 0.001

    def test_parse_short_timestamp(self, worker):
        """Test parsing MM:SS.mmm format (no hours)."""
        result = worker._parse_vtt_timestamp("05:30.500")
        expected = 5 * 60 + 30.5
        assert abs(result - expected) < 0.001

    def test_parse_zero_timestamp(self, worker):
        """Test parsing zero timestamp."""
        result = worker._parse_vtt_timestamp("00:00:00.000")
        assert result == 0.0

    def test_parse_with_whitespace(self, worker):
        """Test parsing timestamp with surrounding whitespace."""
        result = worker._parse_vtt_timestamp("  00:01:00.000  ")
        assert result == 60.0
