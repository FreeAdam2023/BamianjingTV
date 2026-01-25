"""Tests for Item models."""

import pytest
from datetime import datetime

from app.models.source import SourceType
from app.models.item import (
    Item,
    ItemStatus,
    ItemCreate,
    ItemTrigger,
    PipelineStatus,
)


class TestItemStatus:
    """Tests for ItemStatus enum."""

    def test_all_item_statuses_exist(self):
        """Test that all expected item statuses are defined."""
        assert ItemStatus.DISCOVERED == "discovered"
        assert ItemStatus.QUEUED == "queued"
        assert ItemStatus.PROCESSING == "processing"
        assert ItemStatus.COMPLETED == "completed"
        assert ItemStatus.PARTIAL == "partial"
        assert ItemStatus.FAILED == "failed"


class TestPipelineStatus:
    """Tests for PipelineStatus model."""

    def test_create_pipeline_status_minimal(self):
        """Test creating a pipeline status with minimal fields."""
        ps = PipelineStatus(pipeline_id="zh_main")

        assert ps.pipeline_id == "zh_main"
        assert ps.status == "pending"
        assert ps.progress == 0.0
        assert ps.job_id is None
        assert ps.error is None

    def test_create_pipeline_status_with_job(self):
        """Test creating a pipeline status with job info."""
        ps = PipelineStatus(
            pipeline_id="zh_main",
            status="processing",
            progress=0.5,
            job_id="abc123",
        )

        assert ps.status == "processing"
        assert ps.progress == 0.5
        assert ps.job_id == "abc123"


class TestItem:
    """Tests for Item model."""

    def test_create_item_minimal(self):
        """Test creating an item with minimal required fields."""
        item = Item(
            item_id="item_abc123",
            source_type=SourceType.YOUTUBE,
            source_id="yt_lex",
            original_url="https://www.youtube.com/watch?v=abc123",
            original_title="Test Video",
        )

        assert item.item_id == "item_abc123"
        assert item.source_type == SourceType.YOUTUBE
        assert item.source_id == "yt_lex"
        assert item.original_url == "https://www.youtube.com/watch?v=abc123"
        assert item.original_title == "Test Video"
        assert item.status == ItemStatus.DISCOVERED
        assert item.pipelines == {}

    def test_create_item_with_metadata(self):
        """Test creating an item with full metadata."""
        published = datetime(2024, 1, 15, 10, 30, 0)
        item = Item(
            item_id="item_xyz",
            source_type=SourceType.YOUTUBE,
            source_id="yt_channel",
            original_url="https://www.youtube.com/watch?v=xyz",
            original_title="Full Video",
            original_description="A description",
            original_thumbnail="https://img.youtube.com/vi/xyz/0.jpg",
            duration=3600.5,
            published_at=published,
        )

        assert item.original_description == "A description"
        assert item.original_thumbnail == "https://img.youtube.com/vi/xyz/0.jpg"
        assert item.duration == 3600.5
        assert item.published_at == published

    def test_update_pipeline_status_new(self):
        """Test adding a new pipeline status."""
        item = Item(
            item_id="item_test",
            source_type=SourceType.YOUTUBE,
            source_id="yt_test",
            original_url="https://youtube.com/watch?v=test",
            original_title="Test",
        )

        item.update_pipeline_status(
            pipeline_id="zh_main",
            status="processing",
            progress=0.25,
            job_id="job123",
        )

        assert "zh_main" in item.pipelines
        assert item.pipelines["zh_main"].status == "processing"
        assert item.pipelines["zh_main"].progress == 0.25
        assert item.pipelines["zh_main"].job_id == "job123"
        assert item.status == ItemStatus.PROCESSING

    def test_update_pipeline_status_existing(self):
        """Test updating an existing pipeline status."""
        item = Item(
            item_id="item_test",
            source_type=SourceType.YOUTUBE,
            source_id="yt_test",
            original_url="https://youtube.com/watch?v=test",
            original_title="Test",
        )

        # Start processing
        item.update_pipeline_status("zh_main", "processing", 0.25)
        started_at = item.pipelines["zh_main"].started_at

        # Update progress
        item.update_pipeline_status("zh_main", "processing", 0.75)

        assert item.pipelines["zh_main"].progress == 0.75
        assert item.pipelines["zh_main"].started_at == started_at  # Should not change

    def test_update_pipeline_status_completed(self):
        """Test completing a pipeline."""
        item = Item(
            item_id="item_test",
            source_type=SourceType.YOUTUBE,
            source_id="yt_test",
            original_url="https://youtube.com/watch?v=test",
            original_title="Test",
        )

        item.update_pipeline_status("zh_main", "processing", 0.5)
        item.update_pipeline_status("zh_main", "completed", 1.0)

        assert item.pipelines["zh_main"].status == "completed"
        assert item.pipelines["zh_main"].completed_at is not None
        assert item.status == ItemStatus.COMPLETED

    def test_overall_status_partial(self):
        """Test overall status when some pipelines completed."""
        item = Item(
            item_id="item_test",
            source_type=SourceType.YOUTUBE,
            source_id="yt_test",
            original_url="https://youtube.com/watch?v=test",
            original_title="Test",
        )

        item.update_pipeline_status("zh_main", "completed", 1.0)
        item.update_pipeline_status("ja_channel", "pending", 0.0)

        assert item.status == ItemStatus.PARTIAL

    def test_overall_status_failed(self):
        """Test overall status when a pipeline fails."""
        item = Item(
            item_id="item_test",
            source_type=SourceType.YOUTUBE,
            source_id="yt_test",
            original_url="https://youtube.com/watch?v=test",
            original_title="Test",
        )

        item.update_pipeline_status("zh_main", "failed", error="Processing error")

        assert item.status == ItemStatus.FAILED
        assert item.pipelines["zh_main"].error == "Processing error"


class TestItemCreate:
    """Tests for ItemCreate request model."""

    def test_create_item_request_minimal(self):
        """Test creating an ItemCreate request."""
        request = ItemCreate(
            source_type=SourceType.YOUTUBE,
            source_id="yt_test",
            original_url="https://youtube.com/watch?v=test",
            original_title="Test Video",
        )

        assert request.source_type == SourceType.YOUTUBE
        assert request.original_description is None

    def test_create_item_request_full(self):
        """Test creating an ItemCreate request with all fields."""
        published = datetime(2024, 1, 15)
        request = ItemCreate(
            source_type=SourceType.RSS,
            source_id="rss_blog",
            original_url="https://blog.example.com/post",
            original_title="Blog Post",
            original_description="A blog post",
            original_thumbnail="https://blog.example.com/image.jpg",
            duration=600.0,
            published_at=published,
        )

        assert request.source_type == SourceType.RSS
        assert request.duration == 600.0
        assert request.published_at == published


class TestItemTrigger:
    """Tests for ItemTrigger request model."""

    def test_trigger_request(self):
        """Test creating an ItemTrigger request."""
        request = ItemTrigger(
            pipeline_ids=["zh_main", "ja_channel"],
        )

        assert request.pipeline_ids == ["zh_main", "ja_channel"]
