"""Tests for SceneMind SessionManager service."""

import pytest
import tempfile
from pathlib import Path

from app.models.scenemind import (
    SessionCreate,
    SessionStatus,
    ObservationCreate,
    ObservationType,
    CropRegion,
)
from app.services.scenemind.session_manager import SceneMindSessionManager


@pytest.fixture
def temp_dirs():
    """Create temporary directories for session storage."""
    with tempfile.TemporaryDirectory() as sessions_dir:
        with tempfile.TemporaryDirectory() as frames_dir:
            yield Path(sessions_dir), Path(frames_dir)


@pytest.fixture
def session_manager(temp_dirs):
    """Create a session manager with temporary storage."""
    sessions_dir, frames_dir = temp_dirs
    return SceneMindSessionManager(
        sessions_dir=sessions_dir,
        frames_dir=frames_dir,
    )


@pytest.fixture
def sample_session_create():
    """Create sample session data."""
    return SessionCreate(
        show_name="That '70s Show",
        season=1,
        episode=1,
        title="Pilot",
        video_path="/path/to/video.mp4",
        duration=1320.0,
    )


class TestSessionManagerCreate:
    """Tests for session creation."""

    def test_create_session(self, session_manager, sample_session_create):
        """Test creating a new session."""
        session = session_manager.create_session(sample_session_create)

        assert session is not None
        assert session.show_name == "That '70s Show"
        assert session.season == 1
        assert session.episode == 1
        assert session.title == "Pilot"
        assert session.duration == 1320.0
        assert session.status == SessionStatus.WATCHING
        assert session.observation_count == 0

    def test_create_session_generates_id(self, session_manager, sample_session_create):
        """Test that session ID is auto-generated."""
        session = session_manager.create_session(sample_session_create)

        assert session.session_id is not None
        assert len(session.session_id) == 8  # Default ID length

    def test_create_session_persists_to_disk(self, session_manager, sample_session_create, temp_dirs):
        """Test that created session is saved to disk."""
        sessions_dir, _ = temp_dirs
        session = session_manager.create_session(sample_session_create)

        # Check file exists
        file_path = sessions_dir / f"{session.session_id}.json"
        assert file_path.exists()

    def test_create_session_creates_frames_dir(self, session_manager, sample_session_create, temp_dirs):
        """Test that frames directory is created for session."""
        _, frames_dir = temp_dirs
        session = session_manager.create_session(sample_session_create)

        session_frames_dir = frames_dir / session.session_id
        assert session_frames_dir.exists()


class TestSessionManagerRead:
    """Tests for reading sessions."""

    def test_get_session(self, session_manager, sample_session_create):
        """Test getting a session by ID."""
        created = session_manager.create_session(sample_session_create)
        retrieved = session_manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id
        assert retrieved.show_name == created.show_name

    def test_get_session_not_found(self, session_manager):
        """Test getting a non-existent session."""
        result = session_manager.get_session("nonexistent")
        assert result is None

    def test_list_sessions_empty(self, session_manager):
        """Test listing sessions when none exist."""
        result = session_manager.list_sessions()
        assert result == []

    def test_list_sessions(self, session_manager, sample_session_create):
        """Test listing all sessions."""
        session_manager.create_session(sample_session_create)
        session_manager.create_session(
            SessionCreate(
                show_name="Friends",
                season=1,
                episode=1,
                title="Pilot",
                video_path="/path/to/friends.mp4",
                duration=1200.0,
            )
        )

        result = session_manager.list_sessions()
        assert len(result) == 2

    def test_list_sessions_filter_by_status(self, session_manager, sample_session_create):
        """Test filtering sessions by status."""
        session = session_manager.create_session(sample_session_create)
        session_manager.complete_session(session.session_id)

        watching = session_manager.list_sessions(status=SessionStatus.WATCHING)
        completed = session_manager.list_sessions(status=SessionStatus.COMPLETED)

        assert len(watching) == 0
        assert len(completed) == 1

    def test_list_sessions_filter_by_show(self, session_manager, sample_session_create):
        """Test filtering sessions by show name."""
        session_manager.create_session(sample_session_create)
        session_manager.create_session(
            SessionCreate(
                show_name="Friends",
                season=1,
                episode=1,
                title="Pilot",
                video_path="/path/to/friends.mp4",
                duration=1200.0,
            )
        )

        result = session_manager.list_sessions(show_name="That '70s Show")
        assert len(result) == 1
        assert result[0].show_name == "That '70s Show"


class TestSessionManagerUpdate:
    """Tests for updating sessions."""

    def test_update_session_time(self, session_manager, sample_session_create):
        """Test updating session playback time."""
        session = session_manager.create_session(sample_session_create)
        updated = session_manager.update_session_time(session.session_id, 300.0)

        assert updated is not None
        assert updated.current_time == 300.0

    def test_update_session_status(self, session_manager, sample_session_create):
        """Test updating session status."""
        session = session_manager.create_session(sample_session_create)
        updated = session_manager.update_session_status(
            session.session_id, SessionStatus.PAUSED
        )

        assert updated is not None
        assert updated.status == SessionStatus.PAUSED

    def test_complete_session(self, session_manager, sample_session_create):
        """Test marking a session as completed."""
        session = session_manager.create_session(sample_session_create)
        updated = session_manager.complete_session(session.session_id)

        assert updated is not None
        assert updated.status == SessionStatus.COMPLETED

    def test_update_nonexistent_session(self, session_manager):
        """Test updating a non-existent session."""
        result = session_manager.update_session_time("nonexistent", 100.0)
        assert result is None


class TestSessionManagerDelete:
    """Tests for deleting sessions."""

    def test_delete_session(self, session_manager, sample_session_create):
        """Test deleting a session."""
        session = session_manager.create_session(sample_session_create)
        result = session_manager.delete_session(session.session_id)

        assert result is True
        assert session_manager.get_session(session.session_id) is None

    def test_delete_nonexistent_session(self, session_manager):
        """Test deleting a non-existent session."""
        result = session_manager.delete_session("nonexistent")
        assert result is False


class TestObservations:
    """Tests for observation operations."""

    def test_add_observation(self, session_manager, sample_session_create, temp_dirs):
        """Test adding an observation to a session."""
        _, frames_dir = temp_dirs
        session = session_manager.create_session(sample_session_create)

        # Create a dummy frame file
        frame_path = str(frames_dir / session.session_id / "frame_001.png")

        obs_create = ObservationCreate(
            timecode=754.5,
            note="Interesting poster on the wall",
            tag=ObservationType.PROP,
        )

        observation = session_manager.add_observation(
            session.session_id, obs_create, frame_path
        )

        assert observation is not None
        assert observation.timecode == 754.5
        assert observation.note == "Interesting poster on the wall"
        assert observation.tag == ObservationType.PROP
        assert observation.frame_path == frame_path

    def test_add_observation_updates_count(self, session_manager, sample_session_create, temp_dirs):
        """Test that adding observation updates session count."""
        _, frames_dir = temp_dirs
        session = session_manager.create_session(sample_session_create)
        frame_path = str(frames_dir / session.session_id / "frame_001.png")

        obs_create = ObservationCreate(
            timecode=100.0,
            note="Test observation",
            tag=ObservationType.GENERAL,
        )

        session_manager.add_observation(session.session_id, obs_create, frame_path)

        updated_session = session_manager.get_session(session.session_id)
        assert updated_session.observation_count == 1

    def test_add_observation_with_crop(self, session_manager, sample_session_create, temp_dirs):
        """Test adding an observation with crop region."""
        _, frames_dir = temp_dirs
        session = session_manager.create_session(sample_session_create)
        frame_path = str(frames_dir / session.session_id / "frame_001.png")
        crop_path = str(frames_dir / session.session_id / "crop_001.png")

        obs_create = ObservationCreate(
            timecode=100.0,
            note="Cropped observation",
            tag=ObservationType.VISUAL,
            crop_region=CropRegion(x=100, y=100, width=200, height=150),
        )

        observation = session_manager.add_observation(
            session.session_id, obs_create, frame_path, crop_path
        )

        assert observation is not None
        assert observation.crop_path == crop_path
        assert observation.crop_region is not None
        assert observation.crop_region.width == 200

    def test_get_observations(self, session_manager, sample_session_create, temp_dirs):
        """Test getting all observations for a session."""
        _, frames_dir = temp_dirs
        session = session_manager.create_session(sample_session_create)
        frame_path = str(frames_dir / session.session_id / "frame_001.png")

        # Add multiple observations
        for i in range(3):
            obs_create = ObservationCreate(
                timecode=float(i * 100),
                note=f"Observation {i}",
                tag=ObservationType.GENERAL,
            )
            session_manager.add_observation(session.session_id, obs_create, frame_path)

        observations = session_manager.get_observations(session.session_id)
        assert len(observations) == 3

    def test_get_observation(self, session_manager, sample_session_create, temp_dirs):
        """Test getting a specific observation."""
        _, frames_dir = temp_dirs
        session = session_manager.create_session(sample_session_create)
        frame_path = str(frames_dir / session.session_id / "frame_001.png")

        obs_create = ObservationCreate(
            timecode=100.0,
            note="Test",
            tag=ObservationType.GENERAL,
        )
        created = session_manager.add_observation(
            session.session_id, obs_create, frame_path
        )

        retrieved = session_manager.get_observation(session.session_id, created.id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_delete_observation(self, session_manager, sample_session_create, temp_dirs):
        """Test deleting an observation."""
        _, frames_dir = temp_dirs
        session = session_manager.create_session(sample_session_create)
        frame_path = str(frames_dir / session.session_id / "frame_001.png")

        obs_create = ObservationCreate(
            timecode=100.0,
            note="Test",
            tag=ObservationType.GENERAL,
        )
        observation = session_manager.add_observation(
            session.session_id, obs_create, frame_path
        )

        result = session_manager.delete_observation(session.session_id, observation.id)
        assert result is True

        # Verify deleted
        retrieved = session_manager.get_observation(session.session_id, observation.id)
        assert retrieved is None

        # Verify count updated
        updated_session = session_manager.get_session(session.session_id)
        assert updated_session.observation_count == 0


class TestSessionManagerStats:
    """Tests for statistics."""

    def test_get_stats_empty(self, session_manager):
        """Test getting stats when empty."""
        stats = session_manager.get_stats()

        assert stats["total"] == 0
        assert stats["watching"] == 0
        assert stats["completed"] == 0
        assert stats["total_observations"] == 0

    def test_get_stats(self, session_manager, sample_session_create, temp_dirs):
        """Test getting session statistics."""
        _, frames_dir = temp_dirs

        # Create sessions
        s1 = session_manager.create_session(sample_session_create)
        s2 = session_manager.create_session(
            SessionCreate(
                show_name="Friends",
                season=1,
                episode=1,
                title="Pilot",
                video_path="/path/to/friends.mp4",
                duration=1200.0,
            )
        )

        # Complete one session
        session_manager.complete_session(s2.session_id)

        # Add observations to first session
        frame_path = str(frames_dir / s1.session_id / "frame_001.png")
        for _ in range(3):
            obs_create = ObservationCreate(
                timecode=100.0,
                note="Test",
                tag=ObservationType.GENERAL,
            )
            session_manager.add_observation(s1.session_id, obs_create, frame_path)

        stats = session_manager.get_stats()

        assert stats["total"] == 2
        assert stats["watching"] == 1
        assert stats["completed"] == 1
        assert stats["total_observations"] == 3


class TestSessionManagerPersistence:
    """Tests for data persistence across manager instances."""

    def test_reload_sessions(self, temp_dirs, sample_session_create):
        """Test that sessions persist across manager instances."""
        sessions_dir, frames_dir = temp_dirs

        # Create session with first manager
        manager1 = SceneMindSessionManager(
            sessions_dir=sessions_dir,
            frames_dir=frames_dir,
        )
        session = manager1.create_session(sample_session_create)
        session_id = session.session_id

        # Create new manager instance and verify data loads
        manager2 = SceneMindSessionManager(
            sessions_dir=sessions_dir,
            frames_dir=frames_dir,
        )

        loaded = manager2.get_session(session_id)
        assert loaded is not None
        assert loaded.show_name == "That '70s Show"
