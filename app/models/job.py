"""Job data model."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class JobStatus(str, Enum):
    """Job status enum."""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    DIARIZING = "diarizing"
    TRANSLATING = "translating"
    SYNTHESIZING = "synthesizing"
    MUXING = "muxing"
    GENERATING_CONTENT = "generating_content"
    GENERATING_THUMBNAIL = "generating_thumbnail"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class JobCreate(BaseModel):
    """Request model for creating a new job."""

    url: str = Field(..., description="YouTube video URL")
    target_language: str = Field(default="zh", description="Target language code")
    generate_thumbnail: bool = Field(default=True, description="Generate AI thumbnail")
    generate_content: bool = Field(default=True, description="Generate title/description")
    auto_upload: bool = Field(default=False, description="Auto upload to YouTube")
    upload_privacy: str = Field(default="private", description="YouTube privacy status")


class Job(BaseModel):
    """Job data model."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    url: str
    target_language: str = "zh"
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

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
    tts_audio: Optional[str] = None
    output_video: Optional[str] = None
    thumbnail: Optional[str] = None

    # Phase 3: Content generation
    generate_thumbnail: bool = True
    generate_content: bool = True
    auto_upload: bool = False
    upload_privacy: str = "private"

    # Generated content
    title_clickbait: Optional[str] = None
    title_safe: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list] = None
    chapters: Optional[list] = None

    # YouTube upload result
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None

    def get_job_dir(self, base_dir: Path) -> Path:
        """Get the job directory path."""
        return base_dir / self.id

    def update_status(self, status: JobStatus, progress: float = None):
        """Update job status and timestamp."""
        self.status = status
        if progress is not None:
            self.progress = progress
        self.updated_at = datetime.now()
