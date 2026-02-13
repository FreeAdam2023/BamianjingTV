"""Music generation data models."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MusicModelSize(str, Enum):
    """Available MusicGen model sizes."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"

    @property
    def hf_model_id(self) -> str:
        """Get the HuggingFace model ID."""
        return f"facebook/musicgen-{self.value}"


class MusicTrackStatus(str, Enum):
    """Status of a music track."""
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class AmbientMode(str, Enum):
    """Ambient sound mixing mode."""
    MIX = "mix"            # All ambient sounds play simultaneously
    SEQUENCE = "sequence"  # Ambient sounds play in random sequence


class MusicTrack(BaseModel):
    """A generated music track."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    title: str = ""
    prompt: str
    duration_seconds: float = 30.0
    model_size: MusicModelSize = MusicModelSize.MEDIUM
    status: MusicTrackStatus = MusicTrackStatus.GENERATING
    file_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    file_size_bytes: Optional[int] = None
    error: Optional[str] = None
    ambient_sounds: List[str] = []
    ambient_mode: Optional[AmbientMode] = None


class MusicGenerateRequest(BaseModel):
    """Request to generate a music track."""
    prompt: str = Field(..., min_length=1, max_length=1000)
    duration_seconds: float = Field(default=30.0, ge=5.0, le=300.0)
    model_size: MusicModelSize = MusicModelSize.MEDIUM
    title: Optional[str] = None
    ambient_sounds: List[str] = []
    ambient_mode: AmbientMode = AmbientMode.MIX
    ambient_volume: float = Field(default=0.3, ge=0.0, le=1.0)


class MusicGenerateResponse(BaseModel):
    """Response after starting music generation."""
    track: MusicTrack
    message: str = "Music generation started"
