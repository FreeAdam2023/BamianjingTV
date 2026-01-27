"""Tests for Job model, including step timing and cost tracking."""

import pytest
from datetime import datetime
import time

from app.models.job import Job, JobCreate, JobStatus


class TestJobStepTiming:
    """Tests for job step timing tracking."""

    def test_start_step_creates_timing(self):
        """Test that start_step creates a timing entry."""
        job = Job(url="https://example.com/video")

        job.start_step("download")

        assert "download" in job.step_timings
        assert job.step_timings["download"]["started_at"] is not None
        assert job.step_timings["download"]["ended_at"] is None
        assert job.step_timings["download"]["duration_seconds"] is None

    def test_end_step_calculates_duration(self):
        """Test that end_step calculates duration."""
        job = Job(url="https://example.com/video")

        job.start_step("transcribe")
        time.sleep(0.1)  # Small delay
        duration = job.end_step("transcribe")

        assert duration >= 0.1
        assert job.step_timings["transcribe"]["ended_at"] is not None
        assert job.step_timings["transcribe"]["duration_seconds"] >= 0.1

    def test_end_step_without_start_returns_zero(self):
        """Test that end_step returns 0 if step wasn't started."""
        job = Job(url="https://example.com/video")

        duration = job.end_step("nonexistent")

        assert duration == 0.0

    def test_multiple_steps_tracked(self):
        """Test tracking multiple steps."""
        job = Job(url="https://example.com/video")

        job.start_step("download")
        job.end_step("download")
        job.start_step("transcribe")
        job.end_step("transcribe")

        assert "download" in job.step_timings
        assert "transcribe" in job.step_timings
        assert job.step_timings["download"]["duration_seconds"] is not None
        assert job.step_timings["transcribe"]["duration_seconds"] is not None

    def test_total_processing_seconds_calculated(self):
        """Test that total_processing_seconds is calculated correctly."""
        job = Job(url="https://example.com/video")

        job.start_step("step1")
        time.sleep(0.05)
        job.end_step("step1")

        job.start_step("step2")
        time.sleep(0.05)
        job.end_step("step2")

        assert job.total_processing_seconds is not None
        assert job.total_processing_seconds >= 0.1


class TestJobApiCostTracking:
    """Tests for job API cost tracking."""

    def test_add_api_cost(self):
        """Test adding an API cost entry."""
        job = Job(url="https://example.com/video")

        job.add_api_cost(
            service="LLM Translation",
            model="gpt-4o",
            cost_usd=0.05,
            tokens_in=1000,
            tokens_out=500,
        )

        assert len(job.api_costs) == 1
        assert job.api_costs[0]["service"] == "LLM Translation"
        assert job.api_costs[0]["model"] == "gpt-4o"
        assert job.api_costs[0]["cost_usd"] == 0.05
        assert job.api_costs[0]["tokens_in"] == 1000
        assert job.api_costs[0]["tokens_out"] == 500

    def test_total_cost_usd_calculated(self):
        """Test that total_cost_usd is calculated correctly."""
        job = Job(url="https://example.com/video")

        job.add_api_cost(service="Service1", model="model1", cost_usd=0.10)
        job.add_api_cost(service="Service2", model="model2", cost_usd=0.25)

        assert job.total_cost_usd == 0.35

    def test_api_cost_with_audio_seconds(self):
        """Test adding API cost with audio duration."""
        job = Job(url="https://example.com/video")

        job.add_api_cost(
            service="Whisper",
            model="whisper-large-v3",
            cost_usd=0.12,
            audio_seconds=1200.0,
        )

        assert job.api_costs[0]["audio_seconds"] == 1200.0

    def test_api_cost_timestamp_set(self):
        """Test that timestamp is set on API cost entry."""
        job = Job(url="https://example.com/video")

        job.add_api_cost(service="Test", model="test-model", cost_usd=0.01)

        assert job.api_costs[0]["timestamp"] is not None


class TestJobCreateLanguageCodes:
    """Tests for JobCreate with merged Chinese language codes."""

    def test_zh_tw_sets_traditional(self):
        """Test that zh-TW sets use_traditional_chinese to True."""
        job_create = JobCreate(url="https://example.com/video", target_language="zh-TW")

        assert job_create.use_traditional_chinese is True
        assert job_create.target_language == "zh"  # Normalized

    def test_zh_cn_sets_simplified(self):
        """Test that zh-CN sets use_traditional_chinese to False."""
        job_create = JobCreate(url="https://example.com/video", target_language="zh-CN")

        assert job_create.use_traditional_chinese is False
        assert job_create.target_language == "zh"  # Normalized

    def test_legacy_zh_preserved(self):
        """Test that legacy 'zh' language code works with explicit traditional flag."""
        job_create = JobCreate(
            url="https://example.com/video",
            target_language="zh",
            use_traditional_chinese=False,
        )

        assert job_create.use_traditional_chinese is False
        assert job_create.target_language == "zh"

    def test_non_chinese_language(self):
        """Test that non-Chinese languages are preserved."""
        job_create = JobCreate(url="https://example.com/video", target_language="ja")

        assert job_create.target_language == "ja"

    def test_default_language_is_zh_tw(self):
        """Test that default language is zh-TW (Traditional Chinese)."""
        job_create = JobCreate(url="https://example.com/video")

        # Default is zh-TW which normalizes to zh with traditional=True
        assert job_create.target_language == "zh"
        assert job_create.use_traditional_chinese is True


class TestJobStatusUpdate:
    """Tests for job status updates."""

    def test_update_status(self):
        """Test updating job status."""
        job = Job(url="https://example.com/video")

        job.update_status(JobStatus.DOWNLOADING, progress=0.1)

        assert job.status == JobStatus.DOWNLOADING
        assert job.progress == 0.1

    def test_update_status_updates_timestamp(self):
        """Test that updating status updates the updated_at timestamp."""
        job = Job(url="https://example.com/video")
        original_updated_at = job.updated_at

        time.sleep(0.01)
        job.update_status(JobStatus.TRANSCRIBING)

        assert job.updated_at > original_updated_at
