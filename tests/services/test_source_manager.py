"""Tests for SourceManager service."""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

from app.models.source import SourceType, SourceSubType, SourceCreate, SourceUpdate
from app.services.source_manager import SourceManager


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def source_manager(temp_data_dir):
    """Create a SourceManager with temporary storage."""
    with patch("app.services.source_manager.settings") as mock_settings:
        mock_settings.sources_file = temp_data_dir / "sources.json"
        manager = SourceManager()
        yield manager


class TestSourceManager:
    """Tests for SourceManager."""

    def test_create_source(self, source_manager):
        """Test creating a new source."""
        source_create = SourceCreate(
            source_id="yt_test",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Test Channel",
            fetcher="youtube_rss",
        )

        source = source_manager.create_source(source_create)

        assert source.source_id == "yt_test"
        assert source.source_type == SourceType.YOUTUBE
        assert source.display_name == "Test Channel"
        assert source.enabled is True

    def test_create_duplicate_source_raises_error(self, source_manager):
        """Test that creating a duplicate source raises an error."""
        source_create = SourceCreate(
            source_id="yt_test",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Test Channel",
            fetcher="youtube_rss",
        )

        source_manager.create_source(source_create)

        with pytest.raises(ValueError, match="already exists"):
            source_manager.create_source(source_create)

    def test_get_source(self, source_manager):
        """Test getting a source by ID."""
        source_create = SourceCreate(
            source_id="yt_get",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Get Test",
            fetcher="youtube_rss",
        )

        source_manager.create_source(source_create)
        source = source_manager.get_source("yt_get")

        assert source is not None
        assert source.source_id == "yt_get"

    def test_get_nonexistent_source_returns_none(self, source_manager):
        """Test that getting a nonexistent source returns None."""
        source = source_manager.get_source("nonexistent")
        assert source is None

    def test_list_sources(self, source_manager):
        """Test listing sources."""
        # Create multiple sources
        for i in range(3):
            source_create = SourceCreate(
                source_id=f"yt_list_{i}",
                source_type=SourceType.YOUTUBE,
                sub_type=SourceSubType.CHANNEL,
                display_name=f"List Test {i}",
                fetcher="youtube_rss",
            )
            source_manager.create_source(source_create)

        sources = source_manager.list_sources()
        assert len(sources) == 3

    def test_list_sources_filtered_by_type(self, source_manager):
        """Test listing sources filtered by type."""
        # Create YouTube source
        source_manager.create_source(SourceCreate(
            source_id="yt_filter",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="YouTube",
            fetcher="youtube_rss",
        ))

        # Create RSS source
        source_manager.create_source(SourceCreate(
            source_id="rss_filter",
            source_type=SourceType.RSS,
            sub_type=SourceSubType.WEBSITE,
            display_name="RSS",
            fetcher="rss_fetcher",
        ))

        youtube_sources = source_manager.list_sources(source_type=SourceType.YOUTUBE)
        assert len(youtube_sources) == 1
        assert youtube_sources[0].source_id == "yt_filter"

    def test_update_source(self, source_manager):
        """Test updating a source."""
        source_manager.create_source(SourceCreate(
            source_id="yt_update",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Original Name",
            fetcher="youtube_rss",
        ))

        update = SourceUpdate(display_name="Updated Name")
        updated = source_manager.update_source("yt_update", update)

        assert updated is not None
        assert updated.display_name == "Updated Name"

    def test_delete_source(self, source_manager):
        """Test deleting a source."""
        source_manager.create_source(SourceCreate(
            source_id="yt_delete",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Delete Me",
            fetcher="youtube_rss",
        ))

        assert source_manager.delete_source("yt_delete") is True
        assert source_manager.get_source("yt_delete") is None

    def test_delete_nonexistent_source_returns_false(self, source_manager):
        """Test that deleting a nonexistent source returns False."""
        assert source_manager.delete_source("nonexistent") is False

    def test_update_last_fetched(self, source_manager):
        """Test updating last_fetched_at timestamp."""
        source_manager.create_source(SourceCreate(
            source_id="yt_fetch",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Fetch Test",
            fetcher="youtube_rss",
        ))

        # Initially no last_fetched_at
        source = source_manager.get_source("yt_fetch")
        assert source.last_fetched_at is None

        # Update
        source_manager.update_last_fetched("yt_fetch")

        source = source_manager.get_source("yt_fetch")
        assert source.last_fetched_at is not None

    def test_increment_item_count(self, source_manager):
        """Test incrementing item count."""
        source_manager.create_source(SourceCreate(
            source_id="yt_count",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Count Test",
            fetcher="youtube_rss",
        ))

        source = source_manager.get_source("yt_count")
        assert source.item_count == 0

        source_manager.increment_item_count("yt_count", 5)

        source = source_manager.get_source("yt_count")
        assert source.item_count == 5

    def test_get_stats(self, source_manager):
        """Test getting source statistics."""
        source_manager.create_source(SourceCreate(
            source_id="yt_stats",
            source_type=SourceType.YOUTUBE,
            sub_type=SourceSubType.CHANNEL,
            display_name="Stats Test",
            fetcher="youtube_rss",
            enabled=True,
        ))

        source_manager.create_source(SourceCreate(
            source_id="rss_stats",
            source_type=SourceType.RSS,
            sub_type=SourceSubType.WEBSITE,
            display_name="RSS Stats",
            fetcher="rss_fetcher",
            enabled=False,
        ))

        stats = source_manager.get_stats()

        assert stats["total"] == 2
        assert stats["enabled"] == 1
        assert stats["by_type"]["youtube"] == 1
        assert stats["by_type"]["rss"] == 1
