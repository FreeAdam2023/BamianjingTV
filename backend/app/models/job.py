"""Job data model."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, model_validator
import uuid

from app.models.source import SourceType


class JobStatus(str, Enum):
    """Job status enum.

    Simplified for Hardcore Player (learning video factory):
    - Removed TTS, thumbnail, content generation, and upload stages
    - Added AWAITING_REVIEW for human-in-the-loop editing
    - Added EXPORTING for video export with subtitles
    """

    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    TRANSLATING = "translating"
    AWAITING_REVIEW = "awaiting_review"  # Pause for UI review
    EXPORTING = "exporting"  # Video export with subtitles
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"  # User cancelled the job


def infer_source_type_from_url(url: str) -> SourceType:
    """Infer source type from URL for v1 compatibility."""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return SourceType.YOUTUBE
    elif "spotify.com" in url_lower or "anchor.fm" in url_lower:
        return SourceType.PODCAST
    elif url_lower.endswith((".xml", ".rss", "/feed", "/rss")):
        return SourceType.RSS
    elif url_lower.startswith(("file://", "/")):
        return SourceType.LOCAL
    else:
        return SourceType.API


class JobCreate(BaseModel):
    """Request model for creating a new job.

    Simplified for Hardcore Player (learning video factory).
    """

    url: str = Field(..., description="Video URL")
    target_language: str = Field(default="zh", description="Target language code")
    use_traditional_chinese: bool = Field(
        default=True, description="Use Traditional Chinese for subtitles"
    )

    # v2 fields - auto-populated if not provided
    source_type: Optional[SourceType] = Field(default=None, description="Source type")
    source_id: Optional[str] = Field(default=None, description="Source ID")
    item_id: Optional[str] = Field(default=None, description="Item ID")
    pipeline_id: Optional[str] = Field(default=None, description="Pipeline ID")

    @model_validator(mode="after")
    def populate_v2_fields(self) -> "JobCreate":
        """Auto-populate v2 fields for backward compatibility."""
        if self.source_type is None:
            self.source_type = infer_source_type_from_url(self.url)

        if self.source_id is None:
            self.source_id = "legacy"

        if self.item_id is None:
            # Generate item_id from URL hash for deduplication
            import hashlib
            url_hash = hashlib.md5(self.url.encode()).hexdigest()[:8]
            self.item_id = f"item_{url_hash}"

        if self.pipeline_id is None:
            self.pipeline_id = "default_zh"

        return self


class Job(BaseModel):
    """Job data model.

    Simplified for Hardcore Player (learning video factory).
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    url: str
    target_language: str = "zh"
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # ========== v2: Source tracking ==========
    # These fields are auto-populated for backward compatibility with v1 jobs
    source_type: Optional[SourceType] = Field(default=None, description="Source type")
    source_id: Optional[str] = Field(default=None, description="Source ID")
    item_id: Optional[str] = Field(default=None, description="Item ID")
    pipeline_id: Optional[str] = Field(default=None, description="Pipeline ID")

    @model_validator(mode="after")
    def migrate_v1_fields(self) -> "Job":
        """Auto-populate v2 fields when loading v1 jobs."""
        if self.source_type is None:
            self.source_type = infer_source_type_from_url(self.url)

        if self.source_id is None:
            self.source_id = "legacy"

        if self.item_id is None:
            # Use job ID for legacy items
            self.item_id = f"item_{self.id}"

        if self.pipeline_id is None:
            self.pipeline_id = "default_zh"

        return self

    # Metadata from video
    title: Optional[str] = None
    duration: Optional[float] = None
    channel: Optional[str] = None

    # Paths (relative to job directory)
    source_video: Optional[str] = None
    source_audio: Optional[str] = None
    transcript_raw: Optional[str] = None
    transcript_diarized: Optional[str] = None
    translation: Optional[str] = None
    output_video: Optional[str] = None

    # ========== Hardcore Player: Timeline ==========
    timeline_id: Optional[str] = Field(default=None, description="Associated timeline ID")
    use_traditional_chinese: bool = Field(
        default=True, description="Use Traditional Chinese for subtitles"
    )

    # ========== Job Control ==========
    cancel_requested: bool = Field(default=False, description="User requested cancellation")

    def get_job_dir(self, base_dir: Path) -> Path:
        """Get the job directory path."""
        return base_dir / self.id

    def update_status(self, status: JobStatus, progress: float = None):
        """Update job status and timestamp."""
        self.status = status
        if progress is not None:
            self.progress = progress
        self.updated_at = datetime.now()
