"""Tests for Source models."""

import pytest
from datetime import datetime

from app.models.source import (
    Source,
    SourceType,
    SourceSubType,
    SourceCreate,
    SourceUpdate,
)


class TestSourceType:
    """Tests for SourceType enum."""

    def test_all_source_types_exist(self):
        """Test that all expected source types are defined."""
        assert SourceType.YOUTUBE == "youtube"
        assert SourceType.RSS == "rss"
        assert SourceType.PODCAST == "podcast"
        assert SourceType.SCRAPER == "scraper"
        assert SourceType.LOCAL == "local"
        assert SourceType.API == "api"

    def test_source_type_is_string_enum(self):
        """Test that SourceType values can be used as strings."""
        assert SourceType.YOUTUBE.value == "youtube"
        # String comparison works because it's a str enum
        assert SourceType.YOUTUBE == "youtube"


class TestSourceSubType:
    """Tests for SourceSubType enum."""

    def test_youtube_subtypes(self):
        """Test YouTube-related subtypes."""
        assert SourceSubType.CHANNEL == "channel"
        assert SourceSubType.PLAYLIST == "playlist"
        assert SourceSubType.VIDEO == "video"

    def test_rss_subtypes(self):
        """Test RSS-related subtypes."""
        assert SourceSubType.WEBSITE == "website"
        assert SourceSubType.BLOG == "blog"

    def test_podcast_subtypes(self):
        """Test Podcast-related subtypes."""
        assert SourceSubType.SHOW == "show"
        assert SourceSubType.EPISODE == "episode"

    def test_local_subtypes(self):
        """Test Local-related subtypes."""
        assert SourceSubType.FOLDER == "folder"
        assert SourceSubType.FILE == "file"


class TestSource:
    """Tests for Source model."""

    def test_create_source_minimal(self):
        """Test creating a source with minimal required fields."""
        source = Source(
            source_id="yt_lex",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Lex Fridman",
            fetcher="youtube_rss",
        )

        assert source.source_id == "yt_lex"
        assert source.source_type == SourceType.YOUTUBE
        assert source.sub_type == SourceSubType.CHANNEL
        assert source.display_name == "Lex Fridman"
        assert source.fetcher == "youtube_rss"
        assert source.enabled is True
        assert source.config == {}
        assert source.default_pipelines == []
        assert source.item_count == 0
        assert source.last_fetched_at is None

    def test_create_source_with_config(self):
        """Test creating a source with configuration."""
        source = Source(
            source_id="yt_lex",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Lex Fridman",
            fetcher="youtube_rss",
            config={"channel_id": "UCSHZKyawb77ixDdsGog4iWA"},
            default_pipelines=["zh_main", "ja_channel"],
        )

        assert source.config["channel_id"] == "UCSHZKyawb77ixDdsGog4iWA"
        assert source.default_pipelines == ["zh_main", "ja_channel"]

    def test_create_rss_source(self):
        """Test creating an RSS source."""
        source = Source(
            source_id="rss_techcrunch",
            source_type=SourceType.RSS,
            sub_type=SourceSubType.WEBSITE,
            display_name="TechCrunch",
            fetcher="rss_fetcher",
            config={"feed_url": "https://techcrunch.com/feed/"},
        )

        assert source.source_type == SourceType.RSS
        assert source.config["feed_url"] == "https://techcrunch.com/feed/"

    def test_source_created_at_is_set(self):
        """Test that created_at is automatically set."""
        before = datetime.now()
        source = Source(
            source_id="test",
            source_type=SourceType.API,
            sub_type=SourceSubType.VIDEO,
            display_name="Test",
            fetcher="manual",
        )
        after = datetime.now()

        assert before <= source.created_at <= after


class TestSourceCreate:
    """Tests for SourceCreate request model."""

    def test_create_source_request(self):
        """Test creating a SourceCreate request."""
        request = SourceCreate(
            source_id="yt_test",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Test Channel",
            fetcher="youtube_rss",
        )

        assert request.source_id == "yt_test"
        assert request.enabled is True
        assert request.default_pipelines == []


class TestSourceUpdate:
    """Tests for SourceUpdate request model."""

    def test_update_source_partial(self):
        """Test partial update fields."""
        update = SourceUpdate(display_name="New Name")

        assert update.display_name == "New Name"
        assert update.fetcher is None
        assert update.config is None
        assert update.enabled is None

    def test_update_source_full(self):
        """Test full update with all fields."""
        update = SourceUpdate(
            display_name="Updated Name",
            fetcher="new_fetcher",
            config={"new_key": "value"},
            enabled=False,
            default_pipelines=["pipeline1"],
        )

        assert update.display_name == "Updated Name"
        assert update.fetcher == "new_fetcher"
        assert update.config == {"new_key": "value"}
        assert update.enabled is False
        assert update.default_pipelines == ["pipeline1"]
