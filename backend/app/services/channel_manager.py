"""Channel and Publication management service."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.models.channel import (
    Channel,
    ChannelCreate,
    ChannelStatus,
    ChannelSummary,
    ChannelType,
    ChannelUpdate,
    Publication,
    PublicationCreate,
    PublicationStatus,
    PublicationSummary,
    PublicationUpdate,
)


class ChannelManager:
    """Manages publishing channels and publications."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.channels_file = self.data_dir / "channels.json"
        self.publications_dir = self.data_dir / "publications"

        # In-memory cache
        self._channels: Dict[str, Channel] = {}
        self._publications: Dict[str, Publication] = {}

        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.publications_dir.mkdir(parents=True, exist_ok=True)

        # Load data
        self._load_channels()
        self._load_publications()

    # ============ Channel Operations ============

    def _load_channels(self) -> None:
        """Load channels from disk."""
        if not self.channels_file.exists():
            logger.info("No channels file found, starting fresh")
            return

        try:
            with open(self.channels_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data:
                channel = Channel(**item)
                self._channels[channel.channel_id] = channel

            logger.info(f"Loaded {len(self._channels)} channels")
        except Exception as e:
            logger.error(f"Failed to load channels: {e}")

    def _save_channels(self) -> None:
        """Save channels to disk."""
        try:
            data = [ch.model_dump(mode="json") for ch in self._channels.values()]
            with open(self.channels_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            logger.debug(f"Saved {len(self._channels)} channels")
        except Exception as e:
            logger.error(f"Failed to save channels: {e}")

    def list_channels(
        self,
        channel_type: Optional[ChannelType] = None,
        status: Optional[ChannelStatus] = None,
    ) -> List[ChannelSummary]:
        """List all channels."""
        result = []
        for channel in self._channels.values():
            # Filter by type
            if channel_type and channel.type != channel_type:
                continue
            # Filter by status
            if status and channel.status != status:
                continue

            result.append(
                ChannelSummary(
                    channel_id=channel.channel_id,
                    name=channel.name,
                    type=channel.type,
                    status=channel.status,
                    youtube_channel_name=channel.youtube_channel_name,
                    total_publications=channel.total_publications,
                    last_published_at=channel.last_published_at,
                )
            )

        # Sort by name
        result.sort(key=lambda x: x.name)
        return result

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """Get a channel by ID."""
        return self._channels.get(channel_id)

    def create_channel(self, create: ChannelCreate) -> Channel:
        """Create a new channel."""
        channel = Channel(
            name=create.name,
            type=create.type,
            youtube_channel_id=create.youtube_channel_id,
            youtube_credentials_file=create.youtube_credentials_file,
            default_privacy=create.default_privacy,
            default_tags=create.default_tags,
            description_template=create.description_template,
        )

        self._channels[channel.channel_id] = channel
        self._save_channels()

        logger.info(f"Created channel: {channel.channel_id} ({channel.name})")
        return channel

    def update_channel(
        self, channel_id: str, update: ChannelUpdate
    ) -> Optional[Channel]:
        """Update a channel."""
        channel = self.get_channel(channel_id)
        if not channel:
            return None

        if update.name is not None:
            channel.name = update.name
        if update.status is not None:
            channel.status = update.status
        if update.default_privacy is not None:
            channel.default_privacy = update.default_privacy
        if update.default_tags is not None:
            channel.default_tags = update.default_tags
        if update.description_template is not None:
            channel.description_template = update.description_template

        channel.updated_at = datetime.now()
        self._save_channels()

        logger.info(f"Updated channel: {channel_id}")
        return channel

    def delete_channel(self, channel_id: str) -> bool:
        """Delete a channel."""
        if channel_id not in self._channels:
            return False

        del self._channels[channel_id]
        self._save_channels()

        logger.info(f"Deleted channel: {channel_id}")
        return True

    # ============ Publication Operations ============

    def _get_publication_file(self, publication_id: str) -> Path:
        """Get path to publication JSON file."""
        return self.publications_dir / f"{publication_id}.json"

    def _load_publications(self) -> None:
        """Load all publications from disk."""
        for path in self.publications_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                pub = Publication(**data)
                self._publications[pub.publication_id] = pub
            except Exception as e:
                logger.error(f"Failed to load publication {path}: {e}")

        logger.info(f"Loaded {len(self._publications)} publications")

    def _save_publication(self, publication: Publication) -> None:
        """Save a publication to disk."""
        try:
            path = self._get_publication_file(publication.publication_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    publication.model_dump(mode="json"),
                    f,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
        except Exception as e:
            logger.error(f"Failed to save publication {publication.publication_id}: {e}")

    def list_publications(
        self,
        timeline_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        status: Optional[PublicationStatus] = None,
        limit: int = 100,
    ) -> List[PublicationSummary]:
        """List publications with optional filters."""
        result = []

        for pub in self._publications.values():
            # Filter by timeline
            if timeline_id and pub.timeline_id != timeline_id:
                continue
            # Filter by channel
            if channel_id and pub.channel_id != channel_id:
                continue
            # Filter by status
            if status and pub.status != status:
                continue

            # Get channel name
            channel = self.get_channel(pub.channel_id)
            channel_name = channel.name if channel else "Unknown"

            result.append(
                PublicationSummary(
                    publication_id=pub.publication_id,
                    timeline_id=pub.timeline_id,
                    channel_id=pub.channel_id,
                    channel_name=channel_name,
                    title=pub.title,
                    status=pub.status,
                    platform_url=pub.platform_url,
                    platform_views=pub.platform_views,
                    created_at=pub.created_at,
                    published_at=pub.published_at,
                )
            )

        # Sort by created_at descending
        result.sort(key=lambda x: x.created_at, reverse=True)
        return result[:limit]

    def get_publication(self, publication_id: str) -> Optional[Publication]:
        """Get a publication by ID."""
        return self._publications.get(publication_id)

    def create_publication(self, create: PublicationCreate) -> Publication:
        """Create a new publication (draft)."""
        publication = Publication(
            timeline_id=create.timeline_id,
            channel_id=create.channel_id,
            title=create.title,
            description=create.description,
            tags=create.tags,
            privacy=create.privacy,
            thumbnail_main_title=create.thumbnail_main_title,
            thumbnail_sub_title=create.thumbnail_sub_title,
            status=PublicationStatus.DRAFT,
        )

        self._publications[publication.publication_id] = publication
        self._save_publication(publication)

        logger.info(
            f"Created publication draft: {publication.publication_id} "
            f"(timeline={create.timeline_id}, channel={create.channel_id})"
        )
        return publication

    def update_publication(
        self, publication_id: str, update: PublicationUpdate
    ) -> Optional[Publication]:
        """Update a publication."""
        pub = self.get_publication(publication_id)
        if not pub:
            return None

        if update.title is not None:
            pub.title = update.title
        if update.description is not None:
            pub.description = update.description
        if update.tags is not None:
            pub.tags = update.tags
        if update.privacy is not None:
            pub.privacy = update.privacy
        if update.thumbnail_main_title is not None:
            pub.thumbnail_main_title = update.thumbnail_main_title
        if update.thumbnail_sub_title is not None:
            pub.thumbnail_sub_title = update.thumbnail_sub_title

        pub.updated_at = datetime.now()
        self._save_publication(pub)

        logger.info(f"Updated publication: {publication_id}")
        return pub

    def update_publication_status(
        self,
        publication_id: str,
        status: PublicationStatus,
        platform_video_id: Optional[str] = None,
        platform_url: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[Publication]:
        """Update publication status (used during publishing)."""
        pub = self.get_publication(publication_id)
        if not pub:
            return None

        pub.status = status
        pub.updated_at = datetime.now()

        if status == PublicationStatus.PUBLISHED:
            pub.published_at = datetime.now()
            if platform_video_id:
                pub.platform_video_id = platform_video_id
            if platform_url:
                pub.platform_url = platform_url

            # Update channel stats
            channel = self.get_channel(pub.channel_id)
            if channel:
                channel.total_publications += 1
                channel.last_published_at = datetime.now()
                self._save_channels()

        if status == PublicationStatus.FAILED:
            pub.error_message = error_message
            pub.retry_count += 1

        self._save_publication(pub)

        logger.info(f"Updated publication status: {publication_id} -> {status.value}")
        return pub

    def delete_publication(self, publication_id: str) -> bool:
        """Delete a publication."""
        if publication_id not in self._publications:
            return False

        # Remove file
        path = self._get_publication_file(publication_id)
        if path.exists():
            path.unlink()

        del self._publications[publication_id]

        logger.info(f"Deleted publication: {publication_id}")
        return True

    def get_publications_for_timeline(self, timeline_id: str) -> List[PublicationSummary]:
        """Get all publications for a timeline."""
        return self.list_publications(timeline_id=timeline_id)

    def get_publications_for_channel(self, channel_id: str) -> List[PublicationSummary]:
        """Get all publications for a channel."""
        return self.list_publications(channel_id=channel_id)
