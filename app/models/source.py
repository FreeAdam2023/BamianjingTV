"""Source data models for Hardcore Player."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Source type - the entry point of the system's worldview."""
    YOUTUBE = "youtube"       # YouTube videos/channels/playlists
    RSS = "rss"               # Website/blog RSS
    PODCAST = "podcast"       # Podcast RSS
    SCRAPER = "scraper"       # Web scraping
    LOCAL = "local"           # Local files
    API = "api"               # Third-party API


class SourceSubType(str, Enum):
    """Source sub-type for more specific categorization."""
    # YouTube
    CHANNEL = "channel"
    PLAYLIST = "playlist"
    VIDEO = "video"
    # RSS
    WEBSITE = "website"
    BLOG = "blog"
    # Podcast
    SHOW = "show"
    EPISODE = "episode"
    # Local
    FOLDER = "folder"
    FILE = "file"


class Source(BaseModel):
    """Source definition - a specific content source."""
    source_id: str = Field(..., description="Unique identifier, e.g., 'yt_lex'")
    source_type: SourceType = Field(..., description="Source type")
    sub_type: SourceSubType = Field(..., description="Sub-type")
    display_name: str = Field(..., description="Display name, e.g., 'Lex Fridman'")
    fetcher: str = Field(..., description="Fetcher to use, e.g., 'youtube_rss'")

    # Source configuration
    config: dict = Field(
        default_factory=dict,
        description="Fetcher-specific config: YouTube: {channel_id}, RSS: {feed_url}, Local: {watch_path}"
    )

    # Metadata
    enabled: bool = Field(default=True, description="Whether source is enabled")
    created_at: datetime = Field(default_factory=datetime.now)
    last_fetched_at: Optional[datetime] = Field(default=None, description="Last fetch timestamp")
    item_count: int = Field(default=0, description="Total items discovered")

    # Default pipeline configuration
    default_pipelines: List[str] = Field(
        default_factory=list,
        description="Pipeline IDs to auto-trigger for new items"
    )


class SourceCreate(BaseModel):
    """Request model for creating a new source."""
    source_id: str = Field(..., description="Unique identifier")
    source_type: SourceType
    sub_type: SourceSubType
    display_name: str
    fetcher: str
    config: dict = Field(default_factory=dict)
    enabled: bool = True
    default_pipelines: List[str] = Field(default_factory=list)


class SourceUpdate(BaseModel):
    """Request model for updating a source."""
    display_name: Optional[str] = None
    fetcher: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None
    default_pipelines: Optional[List[str]] = None
