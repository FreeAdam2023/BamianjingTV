"""Tests for Timeline model."""

import pytest
from datetime import datetime

from app.models.timeline import (
    SegmentState,
    ExportProfile,
    EditableSegment,
    SegmentUpdate,
    SegmentBatchUpdate,
    Timeline,
    TimelineSummary,
)


class TestEditableSegment:
    """Tests for EditableSegment model."""

    def test_create_segment(self):
        """Test creating an editable segment."""
        seg = EditableSegment(
            id=0,
            start=0.0,
            end=5.0,
            en="Hello world",
            zh="你好世界",
            speaker="SPEAKER_00",
        )
        assert seg.id == 0
        assert seg.start == 0.0
        assert seg.end == 5.0
        assert seg.en == "Hello world"
        assert seg.zh == "你好世界"
        assert seg.speaker == "SPEAKER_00"
        assert seg.state == SegmentState.UNDECIDED
        assert seg.trim_start == 0.0
        assert seg.trim_end == 0.0

    def test_effective_duration(self):
        """Test effective duration calculation with trimming."""
        seg = EditableSegment(
            id=0,
            start=0.0,
            end=10.0,
            en="Test",
            zh="测试",
        )
        assert seg.effective_duration == 10.0

        # With trim
        seg.trim_start = 1.0
        seg.trim_end = 2.0
        assert seg.effective_start == 1.0
        assert seg.effective_end == 8.0
        assert seg.effective_duration == 7.0

    def test_effective_duration_clamped(self):
        """Test that effective duration doesn't go negative."""
        seg = EditableSegment(
            id=0,
            start=0.0,
            end=5.0,
            en="Test",
            zh="测试",
            trim_start=3.0,
            trim_end=3.0,
        )
        assert seg.effective_duration == 0.0


class TestTimeline:
    """Tests for Timeline model."""

    @pytest.fixture
    def sample_segments(self):
        """Create sample segments for testing."""
        return [
            EditableSegment(
                id=0,
                start=0.0,
                end=5.0,
                en="First segment",
                zh="第一段",
                state=SegmentState.KEEP,
            ),
            EditableSegment(
                id=1,
                start=5.0,
                end=10.0,
                en="Second segment",
                zh="第二段",
                state=SegmentState.DROP,
            ),
            EditableSegment(
                id=2,
                start=10.0,
                end=15.0,
                en="Third segment",
                zh="第三段",
                state=SegmentState.UNDECIDED,
            ),
        ]

    def test_create_timeline(self, sample_segments):
        """Test creating a timeline."""
        timeline = Timeline(
            job_id="abc12345",
            source_url="https://youtube.com/watch?v=test",
            source_title="Test Video",
            source_duration=15.0,
            segments=sample_segments,
        )
        assert timeline.job_id == "abc12345"
        assert len(timeline.segments) == 3
        assert not timeline.is_reviewed
        assert timeline.export_profile == ExportProfile.FULL

    def test_segment_counts(self, sample_segments):
        """Test segment count properties."""
        timeline = Timeline(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            segments=sample_segments,
        )
        assert timeline.total_segments == 3
        assert timeline.keep_count == 1
        assert timeline.drop_count == 1
        assert timeline.undecided_count == 1

    def test_review_progress(self, sample_segments):
        """Test review progress calculation."""
        timeline = Timeline(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            segments=sample_segments,
        )
        # 2/3 segments are decided (keep + drop)
        assert abs(timeline.review_progress - 66.67) < 1.0

    def test_keep_duration(self, sample_segments):
        """Test keep duration calculation."""
        timeline = Timeline(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            segments=sample_segments,
        )
        # Only first segment (5s) is marked as KEEP
        assert timeline.keep_duration == 5.0

    def test_get_segment(self, sample_segments):
        """Test getting segment by ID."""
        timeline = Timeline(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            segments=sample_segments,
        )
        seg = timeline.get_segment(1)
        assert seg is not None
        assert seg.en == "Second segment"

        # Non-existent segment
        assert timeline.get_segment(999) is None

    def test_update_segment(self, sample_segments):
        """Test updating a segment."""
        timeline = Timeline(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            segments=sample_segments,
        )
        update = SegmentUpdate(state=SegmentState.KEEP, en="Updated text")
        updated = timeline.update_segment(1, update)

        assert updated is not None
        assert updated.state == SegmentState.KEEP
        assert updated.en == "Updated text"
        assert timeline.keep_count == 2  # Now 2 segments are KEEP

    def test_batch_update_segments(self, sample_segments):
        """Test batch updating segments."""
        timeline = Timeline(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            segments=sample_segments,
        )
        count = timeline.batch_update_segments([0, 1, 2], SegmentState.KEEP)

        assert count == 3
        assert timeline.keep_count == 3
        assert timeline.drop_count == 0
        assert timeline.undecided_count == 0

    def test_mark_reviewed(self, sample_segments):
        """Test marking timeline as reviewed."""
        timeline = Timeline(
            job_id="test",
            source_url="test",
            source_title="Test",
            source_duration=15.0,
            segments=sample_segments,
        )
        assert not timeline.is_reviewed

        timeline.mark_reviewed()
        assert timeline.is_reviewed


class TestSegmentUpdate:
    """Tests for SegmentUpdate model."""

    def test_partial_update(self):
        """Test creating partial update."""
        update = SegmentUpdate(state=SegmentState.KEEP)
        assert update.state == SegmentState.KEEP
        assert update.trim_start is None
        assert update.en is None

    def test_full_update(self):
        """Test creating full update."""
        update = SegmentUpdate(
            state=SegmentState.DROP,
            trim_start=1.0,
            trim_end=2.0,
            en="New English",
            zh="新中文",
        )
        assert update.state == SegmentState.DROP
        assert update.trim_start == 1.0
        assert update.trim_end == 2.0
        assert update.en == "New English"
        assert update.zh == "新中文"


class TestTimelineSummary:
    """Tests for TimelineSummary model."""

    def test_create_summary(self):
        """Test creating timeline summary."""
        summary = TimelineSummary(
            timeline_id="abc123",
            job_id="job456",
            source_title="Test Video",
            source_duration=120.0,
            total_segments=10,
            keep_count=5,
            drop_count=3,
            undecided_count=2,
            review_progress=80.0,
            is_reviewed=False,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert summary.timeline_id == "abc123"
        assert summary.total_segments == 10
        assert summary.review_progress == 80.0
