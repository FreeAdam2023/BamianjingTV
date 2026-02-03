"""Timeline data models for review UI."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


# ============ Observation Types (for WATCHING mode) ============


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


# ============ Segment and Timeline Types ============


class SegmentState(str, Enum):
    """Segment state for review."""

    KEEP = "keep"
    DROP = "drop"
    UNDECIDED = "undecided"


class ExportProfile(str, Enum):
    """Export profile options."""

    FULL = "full"  # Full video with all segments
    ESSENCE = "essence"  # Only keep segments
    BOTH = "both"  # Export both versions


class ExportStatus(str, Enum):
    """Export task status."""

    IDLE = "idle"  # No export running
    EXPORTING = "exporting"  # Rendering video with subtitles
    UPLOADING = "uploading"  # Uploading to YouTube
    COMPLETED = "completed"  # Export finished successfully
    FAILED = "failed"  # Export failed


class EditableSegment(BaseModel):
    """An editable transcript segment for review."""

    id: int
    start: float
    end: float
    en: str  # English original text
    zh: str  # Chinese translation
    speaker: Optional[str] = None
    state: SegmentState = SegmentState.UNDECIDED
    trim_start: float = 0.0  # Trim from segment start (seconds)
    trim_end: float = 0.0  # Trim from segment end (seconds)

    @property
    def effective_start(self) -> float:
        """Get effective start time after trimming."""
        return self.start + self.trim_start

    @property
    def effective_end(self) -> float:
        """Get effective end time after trimming."""
        return self.end - self.trim_end

    @property
    def effective_duration(self) -> float:
        """Get effective duration after trimming."""
        return max(0, self.effective_end - self.effective_start)


class SegmentUpdate(BaseModel):
    """Request model for updating a segment."""

    state: Optional[SegmentState] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    en: Optional[str] = None
    zh: Optional[str] = None


class SegmentBatchUpdate(BaseModel):
    """Request model for batch updating segments."""

    segment_ids: List[int]
    state: SegmentState


class Timeline(BaseModel):
    """Timeline for video segment review and editing."""

    timeline_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    job_id: str
    mode: str = "learning"  # JobMode: learning, watching, dubbing
    source_url: str
    source_title: str
    source_duration: float  # Total video duration in seconds
    segments: List[EditableSegment]
    is_reviewed: bool = False
    export_profile: ExportProfile = ExportProfile.FULL
    use_traditional_chinese: bool = True  # Traditional vs Simplified
    subtitle_area_ratio: float = 0.5  # Ratio of screen height for subtitle area (0.3-0.7)

    # Video-level trim (independent of subtitle segments)
    video_trim_start: float = 0.0  # Trim video from this point (seconds)
    video_trim_end: Optional[float] = None  # Trim video to this point (None = no trim)

    # Speaker names mapping (e.g., {"SPEAKER_0": "Elon Musk", "SPEAKER_1": "Interviewer"})
    speaker_names: Dict[str, str] = Field(default_factory=dict)

    # Output paths (set after export)
    output_full_path: Optional[str] = None
    output_essence_path: Optional[str] = None

    # YouTube upload results
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None

    # Export progress tracking
    export_status: ExportStatus = ExportStatus.IDLE
    export_progress: float = 0.0  # 0-100 percentage
    export_message: Optional[str] = None  # Current step description
    export_error: Optional[str] = None  # Error message if failed
    export_started_at: Optional[datetime] = None

    # Cover frame for thumbnail
    cover_frame_time: Optional[float] = None  # Timestamp of captured cover frame

    # Observations (for WATCHING mode)
    observations: List[Observation] = Field(default_factory=list)

    # AI-generated metadata drafts (saved to avoid re-generation)
    draft_youtube_title: Optional[str] = None
    draft_youtube_description: Optional[str] = None
    draft_youtube_tags: Optional[List[str]] = None
    draft_thumbnail_candidates: Optional[List[dict]] = None  # List of {main, sub, style}
    draft_instruction: Optional[str] = None  # User's AI instruction
    draft_selected_title: Optional[dict] = None  # User's selected title {index, main, sub, style}
    draft_thumbnail_url: Optional[str] = None  # Generated thumbnail URL

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @property
    def total_segments(self) -> int:
        """Get total number of segments."""
        return len(self.segments)

    @property
    def keep_count(self) -> int:
        """Get number of KEEP segments."""
        return sum(1 for seg in self.segments if seg.state == SegmentState.KEEP)

    @property
    def drop_count(self) -> int:
        """Get number of DROP segments."""
        return sum(1 for seg in self.segments if seg.state == SegmentState.DROP)

    @property
    def undecided_count(self) -> int:
        """Get number of UNDECIDED segments."""
        return sum(1 for seg in self.segments if seg.state == SegmentState.UNDECIDED)

    @property
    def keep_duration(self) -> float:
        """Get total duration of KEEP segments."""
        return sum(
            seg.effective_duration
            for seg in self.segments
            if seg.state == SegmentState.KEEP
        )

    @property
    def review_progress(self) -> float:
        """Get review progress as percentage (0-100)."""
        if not self.segments:
            return 100.0
        decided = self.keep_count + self.drop_count
        return (decided / self.total_segments) * 100

    def get_segment(self, segment_id: int) -> Optional[EditableSegment]:
        """Get segment by ID."""
        for seg in self.segments:
            if seg.id == segment_id:
                return seg
        return None

    def update_segment(
        self, segment_id: int, update: SegmentUpdate
    ) -> Optional[EditableSegment]:
        """Update a segment and return the updated segment."""
        seg = self.get_segment(segment_id)
        if not seg:
            return None

        if update.state is not None:
            seg.state = update.state
        if update.trim_start is not None:
            seg.trim_start = update.trim_start
        if update.trim_end is not None:
            seg.trim_end = update.trim_end
        if update.en is not None:
            seg.en = update.en
        if update.zh is not None:
            seg.zh = update.zh

        self.updated_at = datetime.now()
        return seg

    def batch_update_segments(self, segment_ids: List[int], state: SegmentState) -> int:
        """Batch update segment states. Returns number of segments updated."""
        updated = 0
        for seg in self.segments:
            if seg.id in segment_ids:
                seg.state = state
                updated += 1
        if updated > 0:
            self.updated_at = datetime.now()
        return updated

    def mark_reviewed(self) -> None:
        """Mark timeline as reviewed."""
        self.is_reviewed = True
        self.updated_at = datetime.now()

    # ============ Observation Methods (for WATCHING mode) ============

    @property
    def observation_count(self) -> int:
        """Get number of observations."""
        return len(self.observations)

    def get_observation(self, observation_id: str) -> Optional[Observation]:
        """Get observation by ID."""
        for obs in self.observations:
            if obs.id == observation_id:
                return obs
        return None

    def add_observation(self, observation: Observation) -> Observation:
        """Add an observation to the timeline."""
        self.observations.append(observation)
        self.updated_at = datetime.now()
        return observation

    def delete_observation(self, observation_id: str) -> bool:
        """Delete an observation. Returns True if deleted."""
        for i, obs in enumerate(self.observations):
            if obs.id == observation_id:
                del self.observations[i]
                self.updated_at = datetime.now()
                return True
        return False


class TimelineCreate(BaseModel):
    """Request model for creating a timeline (usually auto-created from job)."""

    job_id: str
    mode: str = "learning"  # JobMode: learning, watching, dubbing
    source_url: str
    source_title: str
    source_duration: float


class SubtitleStyleOptions(BaseModel):
    """Subtitle style options for export."""

    en_font_size: int = 40  # English font size in pixels
    zh_font_size: int = 40  # Chinese font size in pixels
    en_color: str = "#ffffff"  # English text color (hex)
    zh_color: str = "#facc15"  # Chinese text color (hex)
    font_weight: str = "500"  # Font weight (400, 500, 600, 700)
    background_color: str = "#1a2744"  # Background color (hex)


class TimelineExportRequest(BaseModel):
    """Request model for triggering export."""

    profile: ExportProfile = ExportProfile.FULL
    use_traditional_chinese: bool = True

    # Subtitle style options
    subtitle_style: Optional[SubtitleStyleOptions] = None

    # YouTube upload options
    upload_to_youtube: bool = False
    youtube_title: Optional[str] = None  # Custom title, defaults to source_title
    youtube_description: Optional[str] = None
    youtube_tags: Optional[List[str]] = None
    youtube_privacy: str = "private"  # private, unlisted, public


class TimelineSummary(BaseModel):
    """Summary of a timeline for list views."""

    timeline_id: str
    job_id: str
    mode: str = "learning"  # JobMode: learning, watching, dubbing
    source_title: str
    source_duration: float
    total_segments: int
    keep_count: int
    drop_count: int
    undecided_count: int
    review_progress: float
    is_reviewed: bool
    # Observation count (for WATCHING mode)
    observation_count: int = 0
    # Export status
    export_status: ExportStatus = ExportStatus.IDLE
    export_progress: float = 0.0
    export_message: Optional[str] = None
    # Timestamps
    created_at: datetime
    updated_at: datetime
