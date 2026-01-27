"""Timeline data models for review UI."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


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
    source_url: str
    source_title: str
    source_duration: float  # Total video duration in seconds
    segments: List[EditableSegment]
    is_reviewed: bool = False
    export_profile: ExportProfile = ExportProfile.FULL
    use_traditional_chinese: bool = True  # Traditional vs Simplified
    subtitle_area_ratio: float = 0.5  # Ratio of screen height for subtitle area (0.3-0.7)

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


class TimelineCreate(BaseModel):
    """Request model for creating a timeline (usually auto-created from job)."""

    job_id: str
    source_url: str
    source_title: str
    source_duration: float


class TimelineExportRequest(BaseModel):
    """Request model for triggering export."""

    profile: ExportProfile = ExportProfile.FULL
    use_traditional_chinese: bool = True

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
    source_title: str
    source_duration: float
    total_segments: int
    keep_count: int
    drop_count: int
    undecided_count: int
    review_progress: float
    is_reviewed: bool
    # Export status
    export_status: ExportStatus = ExportStatus.IDLE
    export_progress: float = 0.0
    export_message: Optional[str] = None
    # Timestamps
    created_at: datetime
    updated_at: datetime
