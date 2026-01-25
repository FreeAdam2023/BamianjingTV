"""Tests for Pipeline models."""

import pytest
from datetime import datetime

from app.models.pipeline import (
    PipelineType,
    PipelineConfig,
    PipelineCreate,
    PipelineUpdate,
    TargetConfig,
    TargetType,
    DEFAULT_PIPELINES,
)


class TestPipelineType:
    """Tests for PipelineType enum."""

    def test_all_pipeline_types_exist(self):
        """Test that all expected pipeline types are defined."""
        assert PipelineType.FULL_DUB == "full_dub"
        assert PipelineType.SUBTITLE_ONLY == "subtitle"
        assert PipelineType.SHORTS == "shorts"
        assert PipelineType.AUDIO_ONLY == "audio"


class TestTargetType:
    """Tests for TargetType enum."""

    def test_all_target_types_exist(self):
        """Test that all expected target types are defined."""
        assert TargetType.YOUTUBE == "youtube"
        assert TargetType.LOCAL == "local"
        assert TargetType.S3 == "s3"
        assert TargetType.FTP == "ftp"


class TestTargetConfig:
    """Tests for TargetConfig model."""

    def test_create_local_target(self):
        """Test creating a local target configuration."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local Output",
        )

        assert target.target_type == TargetType.LOCAL
        assert target.target_id == "output"
        assert target.display_name == "Local Output"
        assert target.privacy_status == "private"
        assert target.auto_publish is False

    def test_create_youtube_target(self):
        """Test creating a YouTube target configuration."""
        target = TargetConfig(
            target_type=TargetType.YOUTUBE,
            target_id="UCxxxxxxxxxxxxxxxx",
            display_name="Chinese Channel",
            privacy_status="unlisted",
            playlist_id="PLxxxxxxxx",
            auto_publish=True,
        )

        assert target.target_type == TargetType.YOUTUBE
        assert target.target_id == "UCxxxxxxxxxxxxxxxx"
        assert target.privacy_status == "unlisted"
        assert target.playlist_id == "PLxxxxxxxx"
        assert target.auto_publish is True

    def test_target_with_custom_config(self):
        """Test target with additional configuration."""
        target = TargetConfig(
            target_type=TargetType.S3,
            target_id="my-bucket",
            display_name="S3 Bucket",
            config={"region": "us-west-2", "prefix": "videos/"},
        )

        assert target.config["region"] == "us-west-2"
        assert target.config["prefix"] == "videos/"


class TestPipelineConfig:
    """Tests for PipelineConfig model."""

    def test_create_pipeline_minimal(self):
        """Test creating a pipeline with minimal fields."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )
        pipeline = PipelineConfig(
            pipeline_id="zh_main",
            pipeline_type=PipelineType.FULL_DUB,
            display_name="Chinese Main",
            target=target,
        )

        assert pipeline.pipeline_id == "zh_main"
        assert pipeline.pipeline_type == PipelineType.FULL_DUB
        assert pipeline.display_name == "Chinese Main"
        assert pipeline.target_language == "zh"
        assert pipeline.generate_thumbnail is True
        assert pipeline.generate_content is True
        assert pipeline.enabled is True
        assert "download" in pipeline.steps
        assert "export" in pipeline.steps

    def test_create_pipeline_full(self):
        """Test creating a pipeline with all options."""
        target = TargetConfig(
            target_type=TargetType.YOUTUBE,
            target_id="channel_id",
            display_name="YouTube Channel",
        )
        pipeline = PipelineConfig(
            pipeline_id="ja_channel",
            pipeline_type=PipelineType.SUBTITLE_ONLY,
            display_name="Japanese Subtitles",
            target_language="ja",
            steps=["download", "transcribe", "translate"],
            generate_thumbnail=False,
            generate_content=False,
            target=target,
            enabled=True,
        )

        assert pipeline.pipeline_id == "ja_channel"
        assert pipeline.target_language == "ja"
        assert pipeline.steps == ["download", "transcribe", "translate"]
        assert pipeline.generate_thumbnail is False
        assert pipeline.generate_content is False

    def test_default_steps(self):
        """Test that default steps are correctly set."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )
        pipeline = PipelineConfig(
            pipeline_id="test",
            pipeline_type=PipelineType.FULL_DUB,
            display_name="Test",
            target=target,
        )

        expected_steps = ["download", "transcribe", "diarize", "translate", "export"]
        assert pipeline.steps == expected_steps


class TestPipelineCreate:
    """Tests for PipelineCreate request model."""

    def test_create_pipeline_request(self):
        """Test creating a PipelineCreate request."""
        target = TargetConfig(
            target_type=TargetType.LOCAL,
            target_id="output",
            display_name="Local",
        )
        request = PipelineCreate(
            pipeline_id="test_pipeline",
            pipeline_type=PipelineType.FULL_DUB,
            display_name="Test Pipeline",
            target=target,
        )

        assert request.pipeline_id == "test_pipeline"
        assert request.target_language == "zh"


class TestPipelineUpdate:
    """Tests for PipelineUpdate request model."""

    def test_update_pipeline_partial(self):
        """Test partial update fields."""
        update = PipelineUpdate(display_name="New Name")

        assert update.display_name == "New Name"
        assert update.target_language is None
        assert update.steps is None

    def test_update_pipeline_full(self):
        """Test full update with all fields."""
        target = TargetConfig(
            target_type=TargetType.YOUTUBE,
            target_id="new_channel",
            display_name="New Channel",
        )
        update = PipelineUpdate(
            display_name="Updated Name",
            target_language="ja",
            steps=["download", "transcribe"],
            generate_thumbnail=False,
            generate_content=False,
            target=target,
            enabled=False,
        )

        assert update.display_name == "Updated Name"
        assert update.target_language == "ja"
        assert update.enabled is False


class TestDefaultPipelines:
    """Tests for default pipeline templates."""

    def test_default_zh_pipeline_exists(self):
        """Test that default_zh pipeline exists."""
        assert "default_zh" in DEFAULT_PIPELINES

    def test_default_zh_pipeline_config(self):
        """Test default_zh pipeline configuration."""
        pipeline = DEFAULT_PIPELINES["default_zh"]

        assert pipeline.pipeline_id == "default_zh"
        assert pipeline.pipeline_type == PipelineType.FULL_DUB
        assert pipeline.target_language == "zh"
        assert pipeline.target.target_type == TargetType.LOCAL
        assert pipeline.target.target_id == "output"
