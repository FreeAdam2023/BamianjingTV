"""Music Commentary Video Factory data models.

Transforms English songs into bilingual learning short videos (3-5 min)
with Chinese narration explaining English lyrics.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class MusicCommentaryStatus(str, Enum):
    """Status of a music commentary session."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    ANNOTATING = "annotating"
    SCRIPTING = "scripting"
    GENERATING_TTS = "generating_tts"
    ASSEMBLING_AUDIO = "assembling_audio"
    GENERATING_VISUAL = "generating_visual"
    GENERATING_METADATA = "generating_metadata"
    AWAITING_REVIEW = "awaiting_review"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class MusicGenre(str, Enum):
    """Music genre classification."""
    POP = "pop"
    ROCK = "rock"
    HIP_HOP = "hip_hop"
    RNB = "rnb"
    COUNTRY = "country"
    INDIE = "indie"
    ELECTRONIC = "electronic"
    JAZZ = "jazz"
    CLASSICAL = "classical"
    OTHER = "other"

    @property
    def label(self) -> str:
        """Human-readable label."""
        labels = {
            "pop": "Pop",
            "rock": "Rock",
            "hip_hop": "Hip Hop",
            "rnb": "R&B",
            "country": "Country",
            "indie": "Indie",
            "electronic": "Electronic",
            "jazz": "Jazz",
            "classical": "Classical",
            "other": "Other",
        }
        return labels[self.value]


class DifficultyLevel(str, Enum):
    """English learning difficulty level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

    @property
    def label(self) -> str:
        """Human-readable label with CEFR mapping."""
        labels = {
            "beginner": "Beginner (A1-A2)",
            "intermediate": "Intermediate (B1-B2)",
            "advanced": "Advanced (C1-C2)",
        }
        return labels[self.value]


class SongConfig(BaseModel):
    """Configuration for the source song."""
    url: str
    title: Optional[str] = None
    artist: Optional[str] = None
    genre: MusicGenre = MusicGenre.POP
    highlight_start: Optional[float] = None  # seconds
    highlight_end: Optional[float] = None  # seconds


class ScriptConfig(BaseModel):
    """Configuration for the commentary script generation."""
    narration_language: str = "zh-CN"
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    max_lyrics_lines: int = Field(default=12, ge=4, le=30)
    target_duration: float = Field(default=240.0, ge=120.0, le=600.0)


class TTSConfig(BaseModel):
    """Configuration for text-to-speech."""
    engine: str = "xtts_v2"
    reference_audio: Optional[str] = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class AudioMixConfig(BaseModel):
    """Configuration for audio mixing."""
    song_volume_during_narration: float = Field(default=0.15, ge=0.0, le=1.0)
    song_volume_during_playback: float = Field(default=0.8, ge=0.0, le=1.0)
    narration_volume: float = Field(default=1.0, ge=0.0, le=2.0)


class YouTubeMetadata(BaseModel):
    """YouTube upload metadata."""
    title: str = ""
    description: str = ""
    tags: List[str] = Field(default_factory=list)
    privacy_status: str = "private"
    category_id: str = "27"  # Education


class LyricsExplanation(BaseModel):
    """Explanation for a single lyrics line."""
    lyric_en: str
    lyric_zh: str
    explanation: str
    vocabulary: List[str] = Field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class CommentaryScript(BaseModel):
    """The generated commentary script."""
    hook_text: str = ""
    background_text: str = ""
    lyrics_explanations: List[LyricsExplanation] = Field(default_factory=list)
    deep_dive_text: str = ""
    outro_text: str = ""


class MusicCommentarySession(BaseModel):
    """A music commentary video generation session."""
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    status: MusicCommentaryStatus = MusicCommentaryStatus.PENDING
    progress: float = Field(default=0.0, ge=0.0, le=100.0)
    error: Optional[str] = None

    # Configuration
    song_config: SongConfig
    script_config: ScriptConfig = Field(default_factory=ScriptConfig)
    tts_config: TTSConfig = Field(default_factory=TTSConfig)
    audio_mix_config: AudioMixConfig = Field(default_factory=AudioMixConfig)
    metadata: YouTubeMetadata = Field(default_factory=YouTubeMetadata)

    # Script (populated after scripting stage)
    script: Optional[CommentaryScript] = None

    # Generated files
    source_audio_path: Optional[str] = None
    source_video_path: Optional[str] = None
    transcript_path: Optional[str] = None
    translation_path: Optional[str] = None
    annotations_path: Optional[str] = None
    script_path: Optional[str] = None
    tts_audio_path: Optional[str] = None
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


class MusicCommentarySessionCreate(BaseModel):
    """Request to create a music commentary session."""
    url: str
    title: Optional[str] = None
    artist: Optional[str] = None
    genre: MusicGenre = MusicGenre.POP
    difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
    max_lyrics_lines: int = Field(default=12, ge=4, le=30)
    target_duration: float = Field(default=240.0, ge=120.0, le=600.0)
    highlight_start: Optional[float] = None
    highlight_end: Optional[float] = None
    triggered_by: str = "manual"


class MusicCommentarySessionUpdate(BaseModel):
    """Request to update a music commentary session's metadata."""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy_status: Optional[str] = None


class MusicGenreInfo(BaseModel):
    """Genre information for API response."""
    value: str
    label: str
