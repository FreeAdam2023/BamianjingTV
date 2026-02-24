"""Lofi Video Factory data models."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class LofiSessionStatus(str, Enum):
    """Status of a lofi session."""
    PENDING = "pending"
    GENERATING_MUSIC = "generating_music"
    MIXING_AUDIO = "mixing_audio"
    GENERATING_VISUALS = "generating_visuals"
    COMPOSITING = "compositing"
    GENERATING_THUMBNAIL = "generating_thumbnail"
    GENERATING_METADATA = "generating_metadata"
    AWAITING_REVIEW = "awaiting_review"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LofiTheme(str, Enum):
    """Available lofi music themes."""
    LOFI_HIP_HOP = "lofi_hip_hop"
    JAZZ = "jazz"
    AMBIENT = "ambient"
    CHILLHOP = "chillhop"
    STUDY = "study"
    SLEEP = "sleep"
    COFFEE_SHOP = "coffee_shop"
    RAIN = "rain"
    NIGHT = "night"
    PIANO = "piano"
    GUITAR = "guitar"

    @property
    def musicgen_prompt(self) -> str:
        """Get MusicGen prompt for this theme."""
        prompts = {
            "lofi_hip_hop": "lofi hip hop beat, chill relaxing study music, vinyl crackle, mellow piano chords, soft drums",
            "jazz": "smooth jazz lofi, saxophone melody, soft piano accompaniment, relaxing cafe atmosphere",
            "ambient": "ambient atmospheric music, ethereal pads, slow evolving textures, meditative calm",
            "chillhop": "chillhop beat, funky bass, smooth rhodes piano, head-nodding groove, laid back",
            "study": "peaceful study music, gentle piano, minimal beats, focus concentration, calm background",
            "sleep": "sleep music, very slow tempo, gentle ambient pads, soothing and peaceful, no drums",
            "coffee_shop": "coffee shop jazz, acoustic guitar, soft brushed drums, warm cozy atmosphere",
            "rain": "rainy day lofi, melancholic piano, soft beats, nostalgic and warm, gentle melody",
            "night": "late night lofi, dark moody chords, slow tempo, city night vibes, atmospheric",
            "piano": "solo piano lofi, gentle keys, minimalist melody, emotional and reflective, slow",
            "guitar": "acoustic guitar lofi, fingerpicking style, warm tone, folk inspired, peaceful",
        }
        return prompts[self.value]

    @property
    def label(self) -> str:
        """Human-readable label."""
        labels = {
            "lofi_hip_hop": "Lofi Hip Hop",
            "jazz": "Jazz",
            "ambient": "Ambient",
            "chillhop": "Chillhop",
            "study": "Study",
            "sleep": "Sleep",
            "coffee_shop": "Coffee Shop",
            "rain": "Rainy Day",
            "night": "Late Night",
            "piano": "Piano",
            "guitar": "Guitar",
        }
        return labels[self.value]


class VisualMode(str, Enum):
    """Visual generation mode."""
    STATIC_KEN_BURNS = "static_ken_burns"
    REMOTION_TEMPLATE = "remotion_template"
    AI_GENERATED = "ai_generated"
    MIXED = "mixed"


class MusicSource(str, Enum):
    """Music generation source."""
    MUSICGEN = "musicgen"
    SUNO = "suno"
    UDIO = "udio"


class MusicConfig(BaseModel):
    """Music generation configuration."""
    source: MusicSource = MusicSource.MUSICGEN
    theme: LofiTheme = LofiTheme.LOFI_HIP_HOP
    custom_prompt: Optional[str] = None
    model_size: str = "medium"
    segment_duration: float = Field(default=120.0, ge=30.0, le=300.0)
    crossfade_duration: float = Field(default=5.0, ge=1.0, le=15.0)
    ambient_sounds: List[str] = Field(default_factory=list)
    ambient_volume: float = Field(default=0.3, ge=0.0, le=1.0)


class VisualConfig(BaseModel):
    """Visual generation configuration."""
    mode: VisualMode = VisualMode.STATIC_KEN_BURNS
    image_path: Optional[str] = None
    ken_burns_speed: float = Field(default=0.0001, ge=0.00001, le=0.001)


class LofiMetadata(BaseModel):
    """YouTube metadata for the session."""
    title: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    privacy_status: str = "private"
    category_id: str = "10"  # Music category
    thumbnail_path: Optional[str] = None


class LofiSession(BaseModel):
    """A lofi video generation session."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    status: LofiSessionStatus = LofiSessionStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    error: Optional[str] = None

    # Duration
    target_duration: float = Field(default=3600.0, ge=300.0, le=10800.0)

    # Configuration
    music_config: MusicConfig = Field(default_factory=MusicConfig)
    visual_config: VisualConfig = Field(default_factory=VisualConfig)
    metadata: LofiMetadata = Field(default_factory=LofiMetadata)

    # Channel
    channel_id: Optional[str] = None

    # Generated files
    music_segments: List[str] = Field(default_factory=list)
    final_audio_path: Optional[str] = None
    final_video_path: Optional[str] = None
    thumbnail_path: Optional[str] = None

    # YouTube
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None

    # Timing
    step_timings: Dict[str, float] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    triggered_by: str = "manual"


class LofiSessionCreate(BaseModel):
    """Request to create a lofi session."""
    target_duration: float = Field(default=3600.0, ge=300.0, le=10800.0)
    theme: LofiTheme = LofiTheme.LOFI_HIP_HOP
    visual_mode: VisualMode = VisualMode.STATIC_KEN_BURNS
    music_source: MusicSource = MusicSource.MUSICGEN
    model_size: str = "medium"
    segment_duration: float = Field(default=120.0, ge=30.0, le=300.0)
    crossfade_duration: float = Field(default=5.0, ge=1.0, le=15.0)
    ambient_sounds: List[str] = Field(default_factory=list)
    ambient_volume: float = Field(default=0.3, ge=0.0, le=1.0)
    image_path: Optional[str] = None
    channel_id: Optional[str] = None
    triggered_by: str = "manual"


class LofiSessionUpdate(BaseModel):
    """Request to update a lofi session's metadata."""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy_status: Optional[str] = None


class LofiThemeInfo(BaseModel):
    """Theme information for API response."""
    value: str
    label: str
    musicgen_prompt: str


class LofiImageInfo(BaseModel):
    """Background image information."""
    name: str
    path: str
    width: Optional[int] = None
    height: Optional[int] = None
