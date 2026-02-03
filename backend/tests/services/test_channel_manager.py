"""Tests for ChannelManager service."""

import pytest
import tempfile
from pathlib import Path

from app.models.channel import (
    ChannelCreate,
    ChannelType,
    ChannelStatus,
    ChannelUpdate,
    PublicationCreate,
    PublicationStatus,
    PublicationUpdate,
)
from app.services.channel_manager import ChannelManager


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def channel_manager(temp_data_dir):
    """Create a channel manager with temporary storage."""
    return ChannelManager(data_dir=temp_data_dir)


@pytest.fixture
def sample_channel_create():
    """Create sample channel data."""
    return ChannelCreate(
        name="My YouTube Channel",
        type=ChannelType.YOUTUBE,
        default_privacy="private",
        default_tags=["education", "language"],
    )


class TestChannelCreate:
    """Tests for creating channels."""

    def test_create_channel(self, channel_manager, sample_channel_create):
        """Test creating a new channel."""
        channel = channel_manager.create_channel(sample_channel_create)

        assert channel is not None
        assert channel.name == "My YouTube Channel"
        assert channel.type == ChannelType.YOUTUBE
        assert channel.status == ChannelStatus.ACTIVE
        assert channel.default_privacy == "private"
        assert "education" in channel.default_tags

    def test_create_channel_generates_id(self, channel_manager, sample_channel_create):
        """Test that channel ID is auto-generated."""
        channel = channel_manager.create_channel(sample_channel_create)

        assert channel.channel_id is not None
        assert len(channel.channel_id) > 0

    def test_create_channel_persists(self, channel_manager, sample_channel_create, temp_data_dir):
        """Test that created channel is saved to disk."""
        channel_manager.create_channel(sample_channel_create)

        file_path = temp_data_dir / "channels.json"
        assert file_path.exists()


class TestChannelRead:
    """Tests for reading channels."""

    def test_get_channel(self, channel_manager, sample_channel_create):
        """Test getting a channel by ID."""
        created = channel_manager.create_channel(sample_channel_create)
        retrieved = channel_manager.get_channel(created.channel_id)

        assert retrieved is not None
        assert retrieved.channel_id == created.channel_id
        assert retrieved.name == created.name

    def test_get_channel_not_found(self, channel_manager):
        """Test getting a non-existent channel."""
        result = channel_manager.get_channel("nonexistent")
        assert result is None

    def test_list_channels_empty(self, channel_manager):
        """Test listing channels when none exist."""
        result = channel_manager.list_channels()
        assert result == []

    def test_list_channels(self, channel_manager, sample_channel_create):
        """Test listing all channels."""
        channel_manager.create_channel(sample_channel_create)
        channel_manager.create_channel(
            ChannelCreate(name="Second Channel", type=ChannelType.YOUTUBE)
        )

        result = channel_manager.list_channels()
        assert len(result) == 2

    def test_list_channels_filter_by_type(self, channel_manager):
        """Test filtering channels by type."""
        channel_manager.create_channel(
            ChannelCreate(name="YouTube", type=ChannelType.YOUTUBE)
        )
        channel_manager.create_channel(
            ChannelCreate(name="Telegram", type=ChannelType.TELEGRAM)
        )

        youtube_channels = channel_manager.list_channels(channel_type=ChannelType.YOUTUBE)
        telegram_channels = channel_manager.list_channels(channel_type=ChannelType.TELEGRAM)

        assert len(youtube_channels) == 1
        assert len(telegram_channels) == 1

    def test_list_channels_filter_by_status(self, channel_manager, sample_channel_create):
        """Test filtering channels by status."""
        channel = channel_manager.create_channel(sample_channel_create)
        channel_manager.update_channel(
            channel.channel_id, ChannelUpdate(status=ChannelStatus.ACTIVE)
        )

        disconnected = channel_manager.list_channels(status=ChannelStatus.DISCONNECTED)
        active = channel_manager.list_channels(status=ChannelStatus.ACTIVE)

        assert len(disconnected) == 0
        assert len(active) == 1


class TestChannelUpdate:
    """Tests for updating channels."""

    def test_update_channel_name(self, channel_manager, sample_channel_create):
        """Test updating channel name."""
        channel = channel_manager.create_channel(sample_channel_create)

        updated = channel_manager.update_channel(
            channel.channel_id, ChannelUpdate(name="New Name")
        )

        assert updated is not None
        assert updated.name == "New Name"

    def test_update_channel_status(self, channel_manager, sample_channel_create):
        """Test updating channel status."""
        channel = channel_manager.create_channel(sample_channel_create)

        updated = channel_manager.update_channel(
            channel.channel_id, ChannelUpdate(status=ChannelStatus.ACTIVE)
        )

        assert updated is not None
        assert updated.status == ChannelStatus.ACTIVE

    def test_update_channel_default_tags(self, channel_manager, sample_channel_create):
        """Test updating channel default tags."""
        channel = channel_manager.create_channel(sample_channel_create)

        updated = channel_manager.update_channel(
            channel.channel_id, ChannelUpdate(default_tags=["new", "tags"])
        )

        assert updated is not None
        assert "new" in updated.default_tags

    def test_update_nonexistent_channel(self, channel_manager):
        """Test updating a non-existent channel."""
        result = channel_manager.update_channel(
            "nonexistent", ChannelUpdate(name="Test")
        )
        assert result is None


class TestChannelDelete:
    """Tests for deleting channels."""

    def test_delete_channel(self, channel_manager, sample_channel_create):
        """Test deleting a channel."""
        channel = channel_manager.create_channel(sample_channel_create)

        result = channel_manager.delete_channel(channel.channel_id)

        assert result is True
        assert channel_manager.get_channel(channel.channel_id) is None

    def test_delete_nonexistent_channel(self, channel_manager):
        """Test deleting a non-existent channel."""
        result = channel_manager.delete_channel("nonexistent")
        assert result is False


class TestPublicationCreate:
    """Tests for creating publications."""

    def test_create_publication(self, channel_manager, sample_channel_create):
        """Test creating a new publication."""
        channel = channel_manager.create_channel(sample_channel_create)

        pub_create = PublicationCreate(
            timeline_id="timeline_123",
            channel_id=channel.channel_id,
            title="My Video",
            description="A great video",
            tags=["video", "test"],
            privacy="private",
        )

        publication = channel_manager.create_publication(pub_create)

        assert publication is not None
        assert publication.timeline_id == "timeline_123"
        assert publication.channel_id == channel.channel_id
        assert publication.title == "My Video"
        assert publication.status == PublicationStatus.DRAFT

    def test_create_publication_generates_id(self, channel_manager, sample_channel_create):
        """Test that publication ID is auto-generated."""
        channel = channel_manager.create_channel(sample_channel_create)

        pub_create = PublicationCreate(
            timeline_id="timeline_123",
            channel_id=channel.channel_id,
            title="Test",
            description="Test description",
        )

        publication = channel_manager.create_publication(pub_create)

        assert publication.publication_id is not None


class TestPublicationRead:
    """Tests for reading publications."""

    def test_get_publication(self, channel_manager, sample_channel_create):
        """Test getting a publication by ID."""
        channel = channel_manager.create_channel(sample_channel_create)
        created = channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_123",
                channel_id=channel.channel_id,
                title="Test",
                description="Test description",
            )
        )

        retrieved = channel_manager.get_publication(created.publication_id)

        assert retrieved is not None
        assert retrieved.publication_id == created.publication_id

    def test_get_publication_not_found(self, channel_manager):
        """Test getting a non-existent publication."""
        result = channel_manager.get_publication("nonexistent")
        assert result is None

    def test_list_publications_empty(self, channel_manager):
        """Test listing publications when none exist."""
        result = channel_manager.list_publications()
        assert result == []

    def test_list_publications(self, channel_manager, sample_channel_create):
        """Test listing all publications."""
        channel = channel_manager.create_channel(sample_channel_create)

        for i in range(3):
            channel_manager.create_publication(
                PublicationCreate(
                    timeline_id=f"timeline_{i}",
                    channel_id=channel.channel_id,
                    title=f"Video {i}",
                    description=f"Description for video {i}",
                )
            )

        result = channel_manager.list_publications()
        assert len(result) == 3

    def test_list_publications_filter_by_timeline(self, channel_manager, sample_channel_create):
        """Test filtering publications by timeline ID."""
        channel = channel_manager.create_channel(sample_channel_create)

        channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_1",
                channel_id=channel.channel_id,
                title="Video 1",
                description="Description 1",
            )
        )
        channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_2",
                channel_id=channel.channel_id,
                title="Video 2",
                description="Description 2",
            )
        )

        result = channel_manager.list_publications(timeline_id="timeline_1")
        assert len(result) == 1
        assert result[0].timeline_id == "timeline_1"

    def test_list_publications_filter_by_channel(self, channel_manager):
        """Test filtering publications by channel ID."""
        channel1 = channel_manager.create_channel(
            ChannelCreate(name="Channel 1", type=ChannelType.YOUTUBE)
        )
        channel2 = channel_manager.create_channel(
            ChannelCreate(name="Channel 2", type=ChannelType.YOUTUBE)
        )

        channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_1",
                channel_id=channel1.channel_id,
                title="Video 1",
                description="Description 1",
            )
        )
        channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_2",
                channel_id=channel2.channel_id,
                title="Video 2",
                description="Description 2",
            )
        )

        result = channel_manager.list_publications(channel_id=channel1.channel_id)
        assert len(result) == 1

    def test_get_publications_for_timeline(self, channel_manager, sample_channel_create):
        """Test getting publications for a timeline."""
        channel = channel_manager.create_channel(sample_channel_create)

        channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_123",
                channel_id=channel.channel_id,
                title="Video",
                description="Test description",
            )
        )

        result = channel_manager.get_publications_for_timeline("timeline_123")
        assert len(result) == 1

    def test_get_publications_for_channel(self, channel_manager, sample_channel_create):
        """Test getting publications for a channel."""
        channel = channel_manager.create_channel(sample_channel_create)

        channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_123",
                channel_id=channel.channel_id,
                title="Video",
                description="Test description",
            )
        )

        result = channel_manager.get_publications_for_channel(channel.channel_id)
        assert len(result) == 1


class TestPublicationUpdate:
    """Tests for updating publications."""

    def test_update_publication(self, channel_manager, sample_channel_create):
        """Test updating a publication."""
        channel = channel_manager.create_channel(sample_channel_create)
        pub = channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_123",
                channel_id=channel.channel_id,
                title="Original Title",
                description="Original description",
            )
        )

        updated = channel_manager.update_publication(
            pub.publication_id,
            PublicationUpdate(
                title="New Title",
                description="New description",
            ),
        )

        assert updated is not None
        assert updated.title == "New Title"
        assert updated.description == "New description"

    def test_update_publication_status_published(self, channel_manager, sample_channel_create):
        """Test updating publication status to published."""
        channel = channel_manager.create_channel(sample_channel_create)
        pub = channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_123",
                channel_id=channel.channel_id,
                title="Video",
                description="Test description",
            )
        )

        updated = channel_manager.update_publication_status(
            pub.publication_id,
            PublicationStatus.PUBLISHED,
            platform_video_id="yt_12345",
            platform_url="https://youtube.com/watch?v=12345",
        )

        assert updated is not None
        assert updated.status == PublicationStatus.PUBLISHED
        assert updated.platform_video_id == "yt_12345"
        assert updated.platform_url == "https://youtube.com/watch?v=12345"
        assert updated.published_at is not None

    def test_update_publication_status_updates_channel_stats(self, channel_manager, sample_channel_create):
        """Test that publishing updates channel statistics."""
        channel = channel_manager.create_channel(sample_channel_create)
        pub = channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_123",
                channel_id=channel.channel_id,
                title="Video",
                description="Test description",
            )
        )

        channel_manager.update_publication_status(
            pub.publication_id,
            PublicationStatus.PUBLISHED,
        )

        updated_channel = channel_manager.get_channel(channel.channel_id)
        assert updated_channel.total_publications == 1
        assert updated_channel.last_published_at is not None

    def test_update_publication_status_failed(self, channel_manager, sample_channel_create):
        """Test updating publication status to failed."""
        channel = channel_manager.create_channel(sample_channel_create)
        pub = channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_123",
                channel_id=channel.channel_id,
                title="Video",
                description="Test description",
            )
        )

        updated = channel_manager.update_publication_status(
            pub.publication_id,
            PublicationStatus.FAILED,
            error_message="Upload failed",
        )

        assert updated is not None
        assert updated.status == PublicationStatus.FAILED
        assert updated.error_message == "Upload failed"
        assert updated.retry_count == 1

    def test_update_nonexistent_publication(self, channel_manager):
        """Test updating a non-existent publication."""
        result = channel_manager.update_publication(
            "nonexistent", PublicationUpdate(title="Test")
        )
        assert result is None


class TestPublicationDelete:
    """Tests for deleting publications."""

    def test_delete_publication(self, channel_manager, sample_channel_create):
        """Test deleting a publication."""
        channel = channel_manager.create_channel(sample_channel_create)
        pub = channel_manager.create_publication(
            PublicationCreate(
                timeline_id="timeline_123",
                channel_id=channel.channel_id,
                title="Video",
                description="Test description",
            )
        )

        result = channel_manager.delete_publication(pub.publication_id)

        assert result is True
        assert channel_manager.get_publication(pub.publication_id) is None

    def test_delete_nonexistent_publication(self, channel_manager):
        """Test deleting a non-existent publication."""
        result = channel_manager.delete_publication("nonexistent")
        assert result is False


class TestChannelManagerPersistence:
    """Tests for data persistence."""

    def test_reload_channels(self, temp_data_dir, sample_channel_create):
        """Test that channels persist across manager instances."""
        # Create channel with first manager
        manager1 = ChannelManager(data_dir=temp_data_dir)
        channel = manager1.create_channel(sample_channel_create)
        channel_id = channel.channel_id

        # Create new manager instance and verify data loads
        manager2 = ChannelManager(data_dir=temp_data_dir)
        loaded = manager2.get_channel(channel_id)

        assert loaded is not None
        assert loaded.name == "My YouTube Channel"

    def test_reload_publications(self, temp_data_dir, sample_channel_create):
        """Test that publications persist across manager instances."""
        # Create channel and publication with first manager
        manager1 = ChannelManager(data_dir=temp_data_dir)
        channel = manager1.create_channel(sample_channel_create)
        pub = manager1.create_publication(
            PublicationCreate(
                timeline_id="timeline_123",
                channel_id=channel.channel_id,
                title="Persistent Video",
                description="Persistent description",
            )
        )
        pub_id = pub.publication_id

        # Create new manager instance and verify data loads
        manager2 = ChannelManager(data_dir=temp_data_dir)
        loaded = manager2.get_publication(pub_id)

        assert loaded is not None
        assert loaded.title == "Persistent Video"
