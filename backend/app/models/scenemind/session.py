"""Session data models for SceneMind watching sessions."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


class SessionStatus(str, Enum):
    """Session status."""

    WATCHING = "watching"
    PAUSED = "paused"
    COMPLETED = "completed"


class Session(BaseModel):
    """A SceneMind watching session for a single episode."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    show_name: str  # e.g., "That '70s Show"
    season: int
    episode: int
    title: str  # Episode title
    video_path: str  # Path to local video file
    duration: float  # Video duration in seconds
    status: SessionStatus = SessionStatus.WATCHING
    current_time: float = 0.0  # Last playback position
    observation_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @property
    def display_name(self) -> str:
        """Get display name for the session."""
        return f"{self.show_name} S{self.season:02d}E{self.episode:02d}"


class SessionCreate(BaseModel):
    """Request model for creating a session."""

    show_name: str
    season: int
    episode: int
    title: str
    video_path: str
    duration: float


class SessionSummary(BaseModel):
    """Summary of a session for list views."""

    session_id: str
    show_name: str
    season: int
    episode: int
    title: str
    duration: float
    status: SessionStatus
    current_time: float
    observation_count: int
    created_at: datetime
    updated_at: datetime

    @property
    def display_name(self) -> str:
        """Get display name for the session."""
        return f"{self.show_name} S{self.season:02d}E{self.episode:02d}"

    @property
    def progress_percent(self) -> float:
        """Get watching progress as percentage."""
        if self.duration <= 0:
            return 0.0
        return min(100.0, (self.current_time / self.duration) * 100)
