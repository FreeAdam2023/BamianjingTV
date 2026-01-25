"""Tests for TimelineManager service."""

import pytest
import tempfile
from pathlib import Path

from app.models.timeline import (
    SegmentState,
    ExportProfile,
    SegmentUpdate,
    Timeline,
)
from app.models.transcript import TranslatedSegment, TranslatedTranscript
from app.services.timeline_manager import TimelineManager


@pytest.fixture
def temp_timelines_dir():
    """Create a temporary directory for timeline storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def timeline_manager(temp_timelines_dir):
    """Create a timeline manager with temporary storage."""
    return TimelineManager(timelines_dir=temp_timelines_dir)


@pytest.fixture
def sample_transcript():
    """Create a sample translated transcript."""
    return TranslatedTranscript(
        source_language="en",
        target_language="zh",
        num_speakers=2,
        segments=[
            TranslatedSegment(
                start=0.0,
                end=5.0,
                text="Hello, welcome to the show.",
                speaker="SPEAKER_00",
                translation="你好，欢迎来到节目。",
            ),
            TranslatedSegment(
                start=5.0,
                end=10.0,
                text="Thank you for having me.",
                speaker="SPEAKER_01",
                translation="谢谢你邀请我。",
            ),
            TranslatedSegment(
                start=10.0,
                end=15.0,
                text="Let's get started.",
                speaker="SPEAKER_00",
                translation="让我们开始吧。",
            ),
        ],
    )


class TestTimelineManagerCreate:
    """Tests for creating timelines."""

    def test_create_from_transcript(self, timeline_manager, sample_transcript):
        """Test creating a timeline from a transcript."""
        timeline = timeline_manager.create_from_transcript(
            job_id="test_job",
            source_url="https://youtube.com/watch?v=test",
            source_title="Test Video",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        assert timeline is not None
        assert timeline.job_id == "test_job"
        assert timeline.source_title == "Test Video"
        assert len(timeline.segments) == 3
        assert all(seg.state == SegmentState.UNDECIDED for seg in timeline.segments)

        # Check segment content
        assert timeline.segments[0].en == "Hello, welcome to the show."
        assert timeline.segments[0].zh == "你好，欢迎来到节目。"
        assert timeline.segments[0].speaker == "SPEAKER_00"

    def test_create_persists_to_disk(
        self, timeline_manager, sample_transcript, temp_timelines_dir
    ):
        """Test that created timeline is saved to disk."""
        timeline = timeline_manager.create_from_transcript(
            job_id="persist_test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        # Check file exists
        file_path = temp_timelines_dir / f"{timeline.timeline_id}.json"
        assert file_path.exists()


class TestTimelineManagerRead:
    """Tests for reading timelines."""

    def test_get_timeline(self, timeline_manager, sample_transcript):
        """Test getting a timeline by ID."""
        created = timeline_manager.create_from_transcript(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        retrieved = timeline_manager.get_timeline(created.timeline_id)
        assert retrieved is not None
        assert retrieved.timeline_id == created.timeline_id

    def test_get_timeline_not_found(self, timeline_manager):
        """Test getting a non-existent timeline."""
        assert timeline_manager.get_timeline("nonexistent") is None

    def test_get_timeline_by_job(self, timeline_manager, sample_transcript):
        """Test getting a timeline by job ID."""
        timeline_manager.create_from_transcript(
            job_id="specific_job",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        retrieved = timeline_manager.get_timeline_by_job("specific_job")
        assert retrieved is not None
        assert retrieved.job_id == "specific_job"

    def test_list_timelines(self, timeline_manager, sample_transcript):
        """Test listing timelines."""
        # Create multiple timelines
        for i in range(3):
            timeline_manager.create_from_transcript(
                job_id=f"job_{i}",
                source_url="test",
                source_title=f"Video {i}",
                source_duration=15.0,
                translated_transcript=sample_transcript,
            )

        summaries = timeline_manager.list_timelines()
        assert len(summaries) == 3

    def test_list_timelines_filtered(self, timeline_manager, sample_transcript):
        """Test listing timelines with filters."""
        # Create reviewed and unreviewed timelines
        t1 = timeline_manager.create_from_transcript(
            job_id="reviewed_job",
            source_url="test",
            source_title="Reviewed",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )
        timeline_manager.mark_reviewed(t1.timeline_id)

        timeline_manager.create_from_transcript(
            job_id="unreviewed_job",
            source_url="test",
            source_title="Unreviewed",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        # Filter by reviewed
        reviewed = timeline_manager.list_timelines(reviewed_only=True)
        assert len(reviewed) == 1
        assert reviewed[0].job_id == "reviewed_job"

        # Filter by unreviewed
        unreviewed = timeline_manager.list_timelines(unreviewed_only=True)
        assert len(unreviewed) == 1
        assert unreviewed[0].job_id == "unreviewed_job"


class TestTimelineManagerUpdate:
    """Tests for updating timelines."""

    def test_update_segment(self, timeline_manager, sample_transcript):
        """Test updating a segment."""
        timeline = timeline_manager.create_from_transcript(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        update = SegmentUpdate(state=SegmentState.KEEP)
        updated = timeline_manager.update_segment(
            timeline.timeline_id, 0, update
        )

        assert updated is not None
        assert updated.state == SegmentState.KEEP

        # Verify persistence
        reloaded = timeline_manager.get_timeline(timeline.timeline_id)
        assert reloaded.segments[0].state == SegmentState.KEEP

    def test_batch_update_segments(self, timeline_manager, sample_transcript):
        """Test batch updating segments."""
        timeline = timeline_manager.create_from_transcript(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        count = timeline_manager.batch_update_segments(
            timeline.timeline_id, [0, 1], SegmentState.KEEP
        )

        assert count == 2

        reloaded = timeline_manager.get_timeline(timeline.timeline_id)
        assert reloaded.segments[0].state == SegmentState.KEEP
        assert reloaded.segments[1].state == SegmentState.KEEP
        assert reloaded.segments[2].state == SegmentState.UNDECIDED

    def test_mark_reviewed(self, timeline_manager, sample_transcript):
        """Test marking timeline as reviewed."""
        timeline = timeline_manager.create_from_transcript(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        result = timeline_manager.mark_reviewed(timeline.timeline_id)
        assert result is True

        reloaded = timeline_manager.get_timeline(timeline.timeline_id)
        assert reloaded.is_reviewed is True

    def test_set_export_profile(self, timeline_manager, sample_transcript):
        """Test setting export profile."""
        timeline = timeline_manager.create_from_transcript(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        result = timeline_manager.set_export_profile(
            timeline.timeline_id, ExportProfile.ESSENCE, use_traditional=False
        )
        assert result is True

        reloaded = timeline_manager.get_timeline(timeline.timeline_id)
        assert reloaded.export_profile == ExportProfile.ESSENCE
        assert reloaded.use_traditional_chinese is False


class TestTimelineManagerDelete:
    """Tests for deleting timelines."""

    def test_delete_timeline(
        self, timeline_manager, sample_transcript, temp_timelines_dir
    ):
        """Test deleting a timeline."""
        timeline = timeline_manager.create_from_transcript(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )
        timeline_id = timeline.timeline_id

        result = timeline_manager.delete_timeline(timeline_id)
        assert result is True

        # Verify deletion
        assert timeline_manager.get_timeline(timeline_id) is None

        # Verify file deleted
        file_path = temp_timelines_dir / f"{timeline_id}.json"
        assert not file_path.exists()

    def test_delete_nonexistent(self, timeline_manager):
        """Test deleting a non-existent timeline."""
        result = timeline_manager.delete_timeline("nonexistent")
        assert result is False


class TestTimelineManagerStats:
    """Tests for timeline statistics."""

    def test_get_stats(self, timeline_manager, sample_transcript):
        """Test getting statistics."""
        # Create some timelines
        t1 = timeline_manager.create_from_transcript(
            job_id="job1",
            source_url="test",
            source_title="Test 1",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )
        timeline_manager.mark_reviewed(t1.timeline_id)

        timeline_manager.create_from_transcript(
            job_id="job2",
            source_url="test",
            source_title="Test 2",
            source_duration=15.0,
            translated_transcript=sample_transcript,
        )

        stats = timeline_manager.get_stats()
        assert stats["total"] == 2
        assert stats["reviewed"] == 1
        assert stats["pending"] == 1
