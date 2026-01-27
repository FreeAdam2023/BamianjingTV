"""Job data model."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
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
    target_language: str = Field(default="zh-TW", description="Target language code (zh-TW, zh-CN, ja, ko, etc.)")
    use_traditional_chinese: bool = Field(
        default=True, description="Use Traditional Chinese for subtitles (derived from target_language)"
    )
    skip_diarization: bool = Field(
        default=False, description="Skip speaker diarization step"
    )

    # v2 fields - auto-populated if not provided
    source_type: Optional[SourceType] = Field(default=None, description="Source type")
    source_id: Optional[str] = Field(default=None, description="Source ID")
    item_id: Optional[str] = Field(default=None, description="Item ID")
    pipeline_id: Optional[str] = Field(default=None, description="Pipeline ID")

    @model_validator(mode="after")
    def populate_v2_fields(self) -> "JobCreate":
        """Auto-populate v2 fields for backward compatibility."""
        # Handle merged Chinese language codes
        if self.target_language == "zh-TW":
            self.use_traditional_chinese = True
            self.target_language = "zh"  # Normalize for processing
        elif self.target_language == "zh-CN":
            self.use_traditional_chinese = False
            self.target_language = "zh"  # Normalize for processing
        elif self.target_language == "zh":
            # Legacy support: use use_traditional_chinese as provided
            pass

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
    skip_diarization: bool = Field(
        default=False, description="Skip speaker diarization step"
    )
    used_youtube_subtitles: bool = Field(
        default=False, description="Whether YouTube subtitles were used instead of Whisper"
    )

    # ========== Job Control ==========
    cancel_requested: bool = Field(default=False, description="User requested cancellation")

    # ========== Processing Stats ==========
    # Step timings: {step_name: {started_at, ended_at, duration_seconds}}
    step_timings: Dict[str, dict] = Field(default_factory=dict, description="Timing for each processing step")
    # API costs: [{service, model, tokens_in, tokens_out, cost_usd, timestamp}]
    api_costs: List[dict] = Field(default_factory=list, description="API call costs")
    # Total processing time in seconds (calculated)
    total_processing_seconds: Optional[float] = Field(default=None, description="Total processing time")
    # Total cost in USD (calculated)
    total_cost_usd: Optional[float] = Field(default=None, description="Total API cost")

    def get_job_dir(self, base_dir: Path) -> Path:
        """Get the job directory path."""
        return base_dir / self.id

    def validate_file_paths(self) -> "Job":
        """Validate file paths exist, clear if not. Returns self for chaining."""
        if self.source_video and not Path(self.source_video).exists():
            self.source_video = None
        if self.source_audio and not Path(self.source_audio).exists():
            self.source_audio = None
        if self.output_video and not Path(self.output_video).exists():
            self.output_video = None
        return self

    def update_status(self, status: JobStatus, progress: float = None):
        """Update job status and timestamp."""
        self.status = status
        if progress is not None:
            self.progress = progress
        self.updated_at = datetime.now()

    def start_step(self, step_name: str) -> None:
        """Record the start time of a processing step."""
        self.step_timings[step_name] = {
            "started_at": datetime.now().isoformat(),
            "ended_at": None,
            "duration_seconds": None,
        }
        self.updated_at = datetime.now()

    def end_step(self, step_name: str) -> float:
        """Record the end time of a processing step. Returns duration in seconds."""
        if step_name not in self.step_timings:
            return 0.0

        started_at = datetime.fromisoformat(self.step_timings[step_name]["started_at"])
        ended_at = datetime.now()
        duration = (ended_at - started_at).total_seconds()

        self.step_timings[step_name]["ended_at"] = ended_at.isoformat()
        self.step_timings[step_name]["duration_seconds"] = duration
        self.updated_at = datetime.now()

        # Update total processing time
        self._recalculate_totals()
        return duration

    def add_api_cost(
        self,
        service: str,
        model: str,
        cost_usd: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
        audio_seconds: float = 0,
        description: str = None,
    ) -> None:
        """Record an API call cost."""
        self.api_costs.append({
            "service": service,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "audio_seconds": audio_seconds,
            "cost_usd": cost_usd,
            "description": description,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()
        self._recalculate_totals()

    def _recalculate_totals(self) -> None:
        """Recalculate total processing time and cost."""
        # Total processing time
        total_seconds = 0.0
        for timing in self.step_timings.values():
            if timing.get("duration_seconds"):
                total_seconds += timing["duration_seconds"]
        self.total_processing_seconds = total_seconds if total_seconds > 0 else None

        # Total cost
        total_cost = sum(c.get("cost_usd", 0) for c in self.api_costs)
        self.total_cost_usd = total_cost if total_cost > 0 else None
