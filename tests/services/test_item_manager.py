"""Tests for ItemManager service."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import datetime

from app.models.source import SourceType
from app.models.item import ItemStatus, ItemCreate
from app.services.item_manager import ItemManager


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def item_manager(temp_data_dir):
    """Create an ItemManager with temporary storage."""
    with patch("app.services.item_manager.settings") as mock_settings:
        mock_settings.items_dir = temp_data_dir / "items"
        mock_settings.items_dir.mkdir(parents=True, exist_ok=True)
        manager = ItemManager()
        yield manager


class TestItemManager:
    """Tests for ItemManager."""

    def test_create_item(self, item_manager):
        """Test creating a new item."""
        item_create = ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_test",
            original_url="https://youtube.com/watch?v=test123",
            original_title="Test Video Title",
        )

        item = item_manager.create_item(item_create)

        assert item.item_id.startswith("item_")
        assert item.source_type == SourceType.YOUTUBE
        assert item.source_id == "yt_test"
        assert item.original_url == "https://youtube.com/watch?v=test123"
        assert item.status == ItemStatus.DISCOVERED

    def test_create_duplicate_item_returns_existing(self, item_manager):
        """Test that creating a duplicate item returns the existing one."""
        item_create = ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_dup",
            original_url="https://youtube.com/watch?v=dup123",
            original_title="Duplicate Video",
        )

        item1 = item_manager.create_item(item_create)
        item2 = item_manager.create_item(item_create)

        assert item1.item_id == item2.item_id

    def test_get_item(self, item_manager):
        """Test getting an item by ID."""
        item_create = ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_get",
            original_url="https://youtube.com/watch?v=get123",
            original_title="Get Test",
        )

        created_item = item_manager.create_item(item_create)
        item = item_manager.get_item(created_item.item_id)

        assert item is not None
        assert item.item_id == created_item.item_id

    def test_get_nonexistent_item_returns_none(self, item_manager):
        """Test that getting a nonexistent item returns None."""
        item = item_manager.get_item("nonexistent")
        assert item is None

    def test_get_item_by_url(self, item_manager):
        """Test getting an item by source ID and URL."""
        item_create = ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_url",
            original_url="https://youtube.com/watch?v=url123",
            original_title="URL Test",
        )

        item_manager.create_item(item_create)
        item = item_manager.get_item_by_url("yt_url", "https://youtube.com/watch?v=url123")

        assert item is not None
        assert item.original_url == "https://youtube.com/watch?v=url123"

    def test_list_items(self, item_manager):
        """Test listing items."""
        for i in range(3):
            item_manager.create_item(ItemCreate(
                source_type=SourceType.YOUTUBE,
                source_id="yt_list",
                original_url=f"https://youtube.com/watch?v=list{i}",
                original_title=f"List Test {i}",
            ))

        items = item_manager.list_items()
        assert len(items) == 3

    def test_list_items_filtered_by_source_type(self, item_manager):
        """Test listing items filtered by source type."""
        item_manager.create_item(ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_filter",
            original_url="https://youtube.com/watch?v=filter1",
            original_title="YouTube Item",
        ))

        item_manager.create_item(ItemCreate(
            source_type=SourceType.RSS,
            source_id="rss_filter",
            original_url="https://blog.example.com/post1",
            original_title="RSS Item",
        ))

        youtube_items = item_manager.list_items(source_type=SourceType.YOUTUBE)
        assert len(youtube_items) == 1
        assert youtube_items[0].source_type == SourceType.YOUTUBE

    def test_list_items_filtered_by_source_id(self, item_manager):
        """Test listing items filtered by source ID."""
        item_manager.create_item(ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_source1",
            original_url="https://youtube.com/watch?v=s1",
            original_title="Source 1 Item",
        ))

        item_manager.create_item(ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_source2",
            original_url="https://youtube.com/watch?v=s2",
            original_title="Source 2 Item",
        ))

        source1_items = item_manager.list_items(source_id="yt_source1")
        assert len(source1_items) == 1

    def test_delete_item(self, item_manager):
        """Test deleting an item."""
        item_create = ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_delete",
            original_url="https://youtube.com/watch?v=delete123",
            original_title="Delete Me",
        )

        item = item_manager.create_item(item_create)
        assert item_manager.delete_item(item.item_id) is True
        assert item_manager.get_item(item.item_id) is None

    def test_update_pipeline_status(self, item_manager):
        """Test updating pipeline status for an item."""
        item = item_manager.create_item(ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_pipeline",
            original_url="https://youtube.com/watch?v=pipeline123",
            original_title="Pipeline Test",
        ))

        item_manager.update_pipeline_status(
            item_id=item.item_id,
            pipeline_id="zh_main",
            status="processing",
            progress=0.5,
            job_id="job123",
        )

        updated_item = item_manager.get_item(item.item_id)
        assert "zh_main" in updated_item.pipelines
        assert updated_item.pipelines["zh_main"].status == "processing"
        assert updated_item.pipelines["zh_main"].progress == 0.5
        assert updated_item.pipelines["zh_main"].job_id == "job123"
        assert updated_item.status == ItemStatus.PROCESSING

    def test_get_fanout_status(self, item_manager):
        """Test getting fan-out status for an item."""
        item = item_manager.create_item(ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_fanout",
            original_url="https://youtube.com/watch?v=fanout123",
            original_title="Fanout Test",
        ))

        item_manager.update_pipeline_status(item.item_id, "zh_main", "completed", 1.0)
        item_manager.update_pipeline_status(item.item_id, "ja_channel", "processing", 0.6)

        fanout = item_manager.get_fanout_status(item.item_id)

        assert fanout is not None
        assert fanout["item_id"] == item.item_id
        assert "zh_main" in fanout["pipelines"]
        assert "ja_channel" in fanout["pipelines"]
        assert fanout["pipelines"]["zh_main"]["status"] == "completed"
        assert fanout["pipelines"]["ja_channel"]["status"] == "processing"

    def test_get_items_by_source(self, item_manager):
        """Test getting all items for a source."""
        for i in range(3):
            item_manager.create_item(ItemCreate(
                source_type=SourceType.YOUTUBE,
                source_id="yt_by_source",
                original_url=f"https://youtube.com/watch?v=source{i}",
                original_title=f"Source Item {i}",
            ))

        items = item_manager.get_items_by_source("yt_by_source")
        assert len(items) == 3

    def test_get_stats(self, item_manager):
        """Test getting item statistics."""
        item_manager.create_item(ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_stats",
            original_url="https://youtube.com/watch?v=stats1",
            original_title="Stats Item 1",
        ))

        item = item_manager.create_item(ItemCreate(
            source_type=SourceType.RSS,
            source_id="rss_stats",
            original_url="https://blog.example.com/stats1",
            original_title="RSS Stats Item",
        ))

        item_manager.update_pipeline_status(item.item_id, "zh_main", "completed", 1.0)

        stats = item_manager.get_stats()

        assert stats["total"] == 2
        assert "youtube" in stats["by_source_type"]
        assert "rss" in stats["by_source_type"]

    def test_get_overview_by_source_type(self, item_manager):
        """Test getting overview statistics by source type."""
        # Create some YouTube items
        for i in range(2):
            item = item_manager.create_item(ItemCreate(
                source_type=SourceType.YOUTUBE,
                source_id="yt_overview",
                original_url=f"https://youtube.com/watch?v=overview{i}",
                original_title=f"Overview Item {i}",
            ))
            if i == 0:
                item_manager.update_pipeline_status(item.item_id, "zh_main", "processing", 0.5)

        overview = item_manager.get_overview_by_source_type()

        assert "youtube" in overview
        assert overview["youtube"]["item_count"] == 2
        assert overview["youtube"]["active_pipelines"] == 1
