"""Observation data models for SceneMind scene captures."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class ObservationType(str, Enum):
    """Type of observation/scene capture."""

    SLANG = "slang"  # Slang expressions, idioms
    PROP = "prop"  # Props, objects in scene
    CHARACTER = "character"  # Character observations
    MUSIC = "music"  # Background music, songs
    VISUAL = "visual"  # Visual gags, cinematography
    GENERAL = "general"  # General observations


class CropRegion(BaseModel):
    """Region for cropped frame capture."""

    x: int
    y: int
    width: int
    height: int


class Observation(BaseModel):
    """A single observation/capture during watching session."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str
    timecode: float  # Timestamp in video (seconds)
    frame_path: str  # Path to full frame capture
    crop_path: Optional[str] = None  # Path to cropped region
    crop_region: Optional[CropRegion] = None
    note: str  # User's note about the observation
    tag: ObservationType = ObservationType.GENERAL
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def timecode_str(self) -> str:
        """Get timecode as HH:MM:SS string."""
        hours = int(self.timecode // 3600)
        minutes = int((self.timecode % 3600) // 60)
        seconds = int(self.timecode % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


class ObservationCreate(BaseModel):
    """Request model for creating an observation."""

    timecode: float
    note: str
    tag: ObservationType = ObservationType.GENERAL
    crop_region: Optional[CropRegion] = None
