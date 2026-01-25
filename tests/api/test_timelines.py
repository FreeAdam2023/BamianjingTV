"""Tests for Timeline API endpoints."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.models.timeline import (
    SegmentState,
    ExportProfile,
    EditableSegment,
    Timeline,
)
from app.models.transcript import TranslatedSegment, TranslatedTranscript
from app.services.timeline_manager import TimelineManager
from app.workers.export import ExportWorker
from app.api.timelines import (
    router,
    set_timeline_manager,
    set_export_worker,
    set_jobs_dir,
)


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as timelines_dir:
        with tempfile.TemporaryDirectory() as jobs_dir:
            yield Path(timelines_dir), Path(jobs_dir)


@pytest.fixture
def timeline_manager(temp_dirs):
    """Create a timeline manager with temporary storage."""
    timelines_dir, _ = temp_dirs
    return TimelineManager(timelines_dir=timelines_dir)


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
                text="Hello world",
                speaker="SPEAKER_00",
                translation="你好世界",
            ),
            TranslatedSegment(
                start=5.0,
                end=10.0,
                text="Goodbye world",
                speaker="SPEAKER_01",
                translation="再见世界",
            ),
        ],
    )


@pytest.fixture
def sample_timeline(timeline_manager, sample_transcript):
    """Create a sample timeline for testing."""
    return timeline_manager.create_from_transcript(
        job_id="test_job",
        source_url="https://youtube.com/watch?v=test",
        source_title="Test Video",
        source_duration=10.0,
        translated_transcript=sample_transcript,
    )


@pytest.fixture
def client(timeline_manager, temp_dirs):
    """Create a test client with the timeline router."""
    from fastapi import FastAPI

    _, jobs_dir = temp_dirs

    app = FastAPI()
    app.include_router(router)

    # Set up module-level dependencies
    set_timeline_manager(timeline_manager)
    set_export_worker(ExportWorker())
    set_jobs_dir(jobs_dir)

    return TestClient(app)


class TestListTimelines:
    """Tests for GET /timelines endpoint."""

    def test_list_empty(self, client):
        """Test listing when no timelines exist."""
        response = client.get("/timelines")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_timelines(self, client, sample_timeline):
        """Test listing timelines."""
        response = client.get("/timelines")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["timeline_id"] == sample_timeline.timeline_id
        assert data[0]["source_title"] == "Test Video"

    def test_list_with_filters(
        self, client, timeline_manager, sample_transcript
    ):
        """Test listing with reviewed/unreviewed filters."""
        # Create reviewed timeline
        t1 = timeline_manager.create_from_transcript(
            job_id="job1",
            source_url="test",
            source_title="Reviewed",
            source_duration=10.0,
            translated_transcript=sample_transcript,
        )
        timeline_manager.mark_reviewed(t1.timeline_id)

        # Create unreviewed timeline
        timeline_manager.create_from_transcript(
            job_id="job2",
            source_url="test",
            source_title="Unreviewed",
            source_duration=10.0,
            translated_transcript=sample_transcript,
        )

        # Test unreviewed_only
        response = client.get("/timelines?unreviewed_only=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["source_title"] == "Unreviewed"


class TestGetTimeline:
    """Tests for GET /timelines/{id} endpoint."""

    def test_get_timeline(self, client, sample_timeline):
        """Test getting a specific timeline."""
        response = client.get(f"/timelines/{sample_timeline.timeline_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["timeline_id"] == sample_timeline.timeline_id
        assert data["job_id"] == "test_job"
        assert len(data["segments"]) == 2

    def test_get_timeline_not_found(self, client):
        """Test getting a non-existent timeline."""
        response = client.get("/timelines/nonexistent")
        assert response.status_code == 404


class TestGetTimelineByJob:
    """Tests for GET /timelines/by-job/{job_id} endpoint."""

    def test_get_by_job(self, client, sample_timeline):
        """Test getting timeline by job ID."""
        response = client.get("/timelines/by-job/test_job")
        assert response.status_code == 200

        data = response.json()
        assert data["job_id"] == "test_job"

    def test_get_by_job_not_found(self, client):
        """Test getting timeline for non-existent job."""
        response = client.get("/timelines/by-job/nonexistent")
        assert response.status_code == 404


class TestUpdateSegment:
    """Tests for PATCH /timelines/{id}/segments/{seg_id} endpoint."""

    def test_update_segment_state(self, client, sample_timeline):
        """Test updating segment state."""
        response = client.patch(
            f"/timelines/{sample_timeline.timeline_id}/segments/0",
            json={"state": "keep"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == 0
        assert data["state"] == "keep"

    def test_update_segment_text(self, client, sample_timeline):
        """Test updating segment text."""
        response = client.patch(
            f"/timelines/{sample_timeline.timeline_id}/segments/0",
            json={"en": "Updated English", "zh": "更新的中文"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["en"] == "Updated English"
        assert data["zh"] == "更新的中文"

    def test_update_segment_not_found(self, client, sample_timeline):
        """Test updating non-existent segment."""
        response = client.patch(
            f"/timelines/{sample_timeline.timeline_id}/segments/999",
            json={"state": "keep"},
        )
        assert response.status_code == 404


class TestBatchUpdateSegments:
    """Tests for POST /timelines/{id}/segments/batch endpoint."""

    def test_batch_update(self, client, sample_timeline):
        """Test batch updating segments."""
        response = client.post(
            f"/timelines/{sample_timeline.timeline_id}/segments/batch",
            json={"segment_ids": [0, 1], "state": "keep"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["updated"] == 2
        assert data["state"] == "keep"


class TestBulkOperations:
    """Tests for bulk segment operations."""

    def test_keep_all(self, client, sample_timeline):
        """Test keeping all segments."""
        response = client.post(
            f"/timelines/{sample_timeline.timeline_id}/segments/keep-all"
        )
        assert response.status_code == 200
        assert response.json()["state"] == "keep"

    def test_drop_all(self, client, sample_timeline):
        """Test dropping all segments."""
        response = client.post(
            f"/timelines/{sample_timeline.timeline_id}/segments/drop-all"
        )
        assert response.status_code == 200
        assert response.json()["state"] == "drop"

    def test_reset_all(self, client, sample_timeline):
        """Test resetting all segments."""
        response = client.post(
            f"/timelines/{sample_timeline.timeline_id}/segments/reset-all"
        )
        assert response.status_code == 200
        assert response.json()["state"] == "undecided"


class TestMarkReviewed:
    """Tests for POST /timelines/{id}/mark-reviewed endpoint."""

    def test_mark_reviewed(self, client, sample_timeline):
        """Test marking timeline as reviewed."""
        response = client.post(
            f"/timelines/{sample_timeline.timeline_id}/mark-reviewed"
        )
        assert response.status_code == 200

    def test_mark_reviewed_not_found(self, client):
        """Test marking non-existent timeline."""
        response = client.post("/timelines/nonexistent/mark-reviewed")
        assert response.status_code == 404


class TestDeleteTimeline:
    """Tests for DELETE /timelines/{id} endpoint."""

    def test_delete_timeline(self, client, sample_timeline):
        """Test deleting a timeline."""
        response = client.delete(
            f"/timelines/{sample_timeline.timeline_id}"
        )
        assert response.status_code == 200

        # Verify deletion
        response = client.get(f"/timelines/{sample_timeline.timeline_id}")
        assert response.status_code == 404

    def test_delete_not_found(self, client):
        """Test deleting non-existent timeline."""
        response = client.delete("/timelines/nonexistent")
        assert response.status_code == 404


class TestTimelineStats:
    """Tests for GET /timelines/stats endpoint."""

    def test_get_stats(self, client, timeline_manager, sample_transcript):
        """Test getting timeline statistics."""
        # Create some timelines
        t1 = timeline_manager.create_from_transcript(
            job_id="job1",
            source_url="test",
            source_title="Test 1",
            source_duration=10.0,
            translated_transcript=sample_transcript,
        )
        timeline_manager.mark_reviewed(t1.timeline_id)

        timeline_manager.create_from_transcript(
            job_id="job2",
            source_url="test",
            source_title="Test 2",
            source_duration=10.0,
            translated_transcript=sample_transcript,
        )

        response = client.get("/timelines/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 2
        assert data["reviewed"] == 1
        assert data["pending"] == 1
