"""Tests for PipelineManager service."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.models.pipeline import (
    PipelineType,
    PipelineCreate,
    PipelineUpdate,
    TargetConfig,
    TargetType,
)
from app.services.pipeline_manager import PipelineManager


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def pipeline_manager(temp_data_dir):
    """Create a PipelineManager with temporary storage."""
    with patch("app.services.pipeline_manager.settings") as mock_settings:
        mock_settings.pipelines_file = temp_data_dir / "pipelines.json"
        manager = PipelineManager()
        yield manager


class TestPipelineManager:
    """Tests for PipelineManager."""

    def test_default_pipeline_exists(self, pipeline_manager):
        """Test that default_zh pipeline exists on initialization."""
        pipeline = pipeline_manager.get_pipeline("default_zh")

        assert pipeline is not None
        assert pipeline.pipeline_id == "default_zh"
        assert pipeline.target_language == "zh"

    def test_create_pipeline(self, pipeline_manager):
        """Test creating a new pipeline."""
        target = TargetConfig(
            target_type=TargetType.YOUTUBE,
            target_id="UC123456",
            display_name="Test Channel",
        )

        pipeline_create = PipelineCreate(
            pipeline_id="test_pipeline",
            pipeline_type=PipelineType.FULL_DUB,
            display_name="Test Pipeline",
            target=target,
        )

        pipeline = pipeline_manager.create_pipeline(pipeline_create)

        assert pipeline.pipeline_id == "test_pipeline"
        assert pipeline.pipeline_type == PipelineType.FULL_DUB
        assert pipeline.display_name == "Test Pipeline"
        assert pipeline.target.target_type == TargetType.YOUTUBE

    def test_create_duplicate_pipeline_raises_error(self, pipeline_manager):
        """Test that creating a duplicate pipeline raises an error."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )

        pipeline_create = PipelineCreate(
            pipeline_id="dup_pipeline",
            pipeline_type=PipelineType.FULL_DUB,
            display_name="Duplicate",
            target=target,
        )

        pipeline_manager.create_pipeline(pipeline_create)

        with pytest.raises(ValueError, match="already exists"):
            pipeline_manager.create_pipeline(pipeline_create)

    def test_get_pipeline(self, pipeline_manager):
        """Test getting a pipeline by ID."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )

        pipeline_manager.create_pipeline(PipelineCreate(
            pipeline_id="get_test",
            pipeline_type=PipelineType.FULL_DUB,
            display_name="Get Test",
            target=target,
        ))

        pipeline = pipeline_manager.get_pipeline("get_test")

        assert pipeline is not None
        assert pipeline.pipeline_id == "get_test"

    def test_get_nonexistent_pipeline_returns_none(self, pipeline_manager):
        """Test that getting a nonexistent pipeline returns None."""
        pipeline = pipeline_manager.get_pipeline("nonexistent")
        assert pipeline is None

    def test_list_pipelines(self, pipeline_manager):
        """Test listing pipelines."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )

        for i in range(3):
            pipeline_manager.create_pipeline(PipelineCreate(
                pipeline_id=f"list_test_{i}",
                pipeline_type=PipelineType.FULL_DUB,
                display_name=f"List Test {i}",
                target=target,
            ))

        # Should include default_zh plus 3 new ones
        pipelines = pipeline_manager.list_pipelines()
        assert len(pipelines) >= 4

    def test_list_pipelines_filtered_by_type(self, pipeline_manager):
        """Test listing pipelines filtered by type."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )

        # Create a subtitle-only pipeline (use different ID to avoid conflict with default)
        pipeline_manager.create_pipeline(PipelineCreate(
            pipeline_id="subtitle_test_filter",
            pipeline_type=PipelineType.SUBTITLE_ONLY,
            display_name="Subtitle Test",
            target=target,
        ))

        subtitle_pipelines = pipeline_manager.list_pipelines(
            pipeline_type=PipelineType.SUBTITLE_ONLY
        )

        # At least 2: the default "subtitle_only" + our new one
        assert len(subtitle_pipelines) >= 2
        assert all(p.pipeline_type == PipelineType.SUBTITLE_ONLY for p in subtitle_pipelines)

    def test_update_pipeline(self, pipeline_manager):
        """Test updating a pipeline."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )

        pipeline_manager.create_pipeline(PipelineCreate(
            pipeline_id="update_test",
            pipeline_type=PipelineType.FULL_DUB,
            display_name="Original Name",
            target=target,
        ))

        update = PipelineUpdate(
            display_name="Updated Name",
            target_language="ja",
        )
        updated = pipeline_manager.update_pipeline("update_test", update)

        assert updated is not None
        assert updated.display_name == "Updated Name"
        assert updated.target_language == "ja"

    def test_delete_pipeline(self, pipeline_manager):
        """Test deleting a pipeline."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )

        pipeline_manager.create_pipeline(PipelineCreate(
            pipeline_id="delete_test",
            pipeline_type=PipelineType.FULL_DUB,
            display_name="Delete Me",
            target=target,
        ))

        assert pipeline_manager.delete_pipeline("delete_test") is True
        assert pipeline_manager.get_pipeline("delete_test") is None

    def test_cannot_delete_default_pipeline(self, pipeline_manager):
        """Test that default pipelines cannot be deleted."""
        assert pipeline_manager.delete_pipeline("default_zh") is False
        assert pipeline_manager.get_pipeline("default_zh") is not None

    def test_delete_nonexistent_pipeline_returns_false(self, pipeline_manager):
        """Test that deleting a nonexistent pipeline returns False."""
        assert pipeline_manager.delete_pipeline("nonexistent") is False

    def test_get_pipelines_for_target(self, pipeline_manager):
        """Test getting pipelines for a specific target type."""
        yt_target = TargetConfig(
            target_type=TargetType.YOUTUBE,
            target_id="UC123",
            display_name="YouTube",
        )

        pipeline_manager.create_pipeline(PipelineCreate(
            pipeline_id="yt_pipeline",
            pipeline_type=PipelineType.FULL_DUB,
            display_name="YouTube Pipeline",
            target=yt_target,
        ))

        youtube_pipelines = pipeline_manager.get_pipelines_for_target(TargetType.YOUTUBE)

        assert len(youtube_pipelines) >= 1
        assert all(p.target.target_type == TargetType.YOUTUBE for p in youtube_pipelines)

    def test_get_stats(self, pipeline_manager):
        """Test getting pipeline statistics."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )

        pipeline_manager.create_pipeline(PipelineCreate(
            pipeline_id="stats_test",
            pipeline_type=PipelineType.SUBTITLE_ONLY,
            display_name="Stats Test",
            target=target,
            enabled=False,
        ))

        stats = pipeline_manager.get_stats()

        assert stats["total"] >= 2  # default_zh + stats_test
        assert "full_dub" in stats["by_type"]
        assert "subtitle" in stats["by_type"]
        assert "local" in stats["by_target"]

    def test_pipeline_with_custom_steps(self, pipeline_manager):
        """Test creating a pipeline with custom steps."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )

        custom_steps = ["download", "transcribe", "translate"]

        pipeline_manager.create_pipeline(PipelineCreate(
            pipeline_id="custom_steps",
            pipeline_type=PipelineType.SUBTITLE_ONLY,
            display_name="Custom Steps",
            steps=custom_steps,
            target=target,
        ))

        pipeline = pipeline_manager.get_pipeline("custom_steps")

        assert pipeline.steps == custom_steps
