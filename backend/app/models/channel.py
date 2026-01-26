"""Publishing channel and publication models."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


class ChannelType(str, Enum):
    """Supported channel types."""
    YOUTUBE = "youtube"
    TELEGRAM = "telegram"  # Future support
    BILIBILI = "bilibili"  # Future support


class ChannelStatus(str, Enum):
    """Channel connection status."""
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class Channel(BaseModel):
    """A publishing channel (YouTube account, Telegram group, etc.)."""

    channel_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str  # Display name (e.g., "主频道", "英语学习频道")
    type: ChannelType
    status: ChannelStatus = ChannelStatus.ACTIVE

    # YouTube specific
    youtube_channel_id: Optional[str] = None  # YouTube's channel ID
    youtube_channel_name: Optional[str] = None  # YouTube channel name
    youtube_credentials_file: Optional[str] = None  # Path to OAuth credentials

    # OAuth status
    is_authorized: bool = False  # Whether OAuth is complete
    oauth_token_file: Optional[str] = None  # Path to channel-specific token file
    authorized_at: Optional[datetime] = None  # When authorization completed

    # Telegram specific (future)
    telegram_chat_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None

    # Default settings for this channel
    default_privacy: str = "private"  # private, unlisted, public
    default_tags: List[str] = Field(default_factory=list)
    description_template: Optional[str] = None  # Template for descriptions

    # Stats
    total_publications: int = 0
    last_published_at: Optional[datetime] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PublicationStatus(str, Enum):
    """Publication status."""
    DRAFT = "draft"  # Metadata prepared but not published
    PUBLISHING = "publishing"  # Currently uploading
    PUBLISHED = "published"  # Successfully published
    FAILED = "failed"  # Publication failed
    DELETED = "deleted"  # Deleted from platform


class Publication(BaseModel):
    """Record of a video published to a channel."""

    publication_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timeline_id: str  # Source timeline
    channel_id: str  # Target channel

    status: PublicationStatus = PublicationStatus.DRAFT

    # Channel-specific metadata
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    privacy: str = "private"

    # Thumbnail
    thumbnail_main_title: Optional[str] = None
    thumbnail_sub_title: Optional[str] = None
    thumbnail_url: Optional[str] = None

    # Publication result
    platform_video_id: Optional[str] = None  # e.g., YouTube video ID
    platform_url: Optional[str] = None  # e.g., YouTube URL
    platform_views: int = 0
    platform_likes: int = 0

    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.now)


class ChannelCreate(BaseModel):
    """Request to create a channel."""
    name: str
    type: ChannelType
    youtube_channel_id: Optional[str] = None
    youtube_credentials_file: Optional[str] = None
    default_privacy: str = "private"
    default_tags: List[str] = Field(default_factory=list)
    description_template: Optional[str] = None


class ChannelUpdate(BaseModel):
    """Request to update a channel."""
    name: Optional[str] = None
    status: Optional[ChannelStatus] = None
    default_privacy: Optional[str] = None
    default_tags: Optional[List[str]] = None
    description_template: Optional[str] = None


class PublicationCreate(BaseModel):
    """Request to create a publication (draft)."""
    timeline_id: str
    channel_id: str
    title: str
    description: str
    tags: List[str] = Field(default_factory=list)
    privacy: str = "private"
    thumbnail_main_title: Optional[str] = None
    thumbnail_sub_title: Optional[str] = None


class PublicationUpdate(BaseModel):
    """Request to update a publication."""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy: Optional[str] = None
    thumbnail_main_title: Optional[str] = None
    thumbnail_sub_title: Optional[str] = None


class ChannelSummary(BaseModel):
    """Summary of a channel for list views."""
    channel_id: str
    name: str
    type: ChannelType
    status: ChannelStatus
    youtube_channel_name: Optional[str] = None
    total_publications: int
    last_published_at: Optional[datetime] = None


class PublicationSummary(BaseModel):
    """Summary of a publication for list views."""
    publication_id: str
    timeline_id: str
    channel_id: str
    channel_name: str
    title: str
    status: PublicationStatus
    platform_url: Optional[str] = None
    platform_views: int = 0
    created_at: datetime
    published_at: Optional[datetime] = None
