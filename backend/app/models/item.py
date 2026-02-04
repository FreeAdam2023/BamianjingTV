"""Item data models for SceneMind."""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field

from app.models.source import SourceType


class ItemStatus(str, Enum):
    """Item status enum."""
    DISCOVERED = "discovered"    # Just discovered
    QUEUED = "queued"            # Queued for processing
    PROCESSING = "processing"    # Currently processing
    COMPLETED = "completed"      # All pipelines completed
    PARTIAL = "partial"          # Some pipelines completed
    FAILED = "failed"            # Failed


class PipelineStatus(BaseModel):
    """Pipeline execution status for an item."""
    pipeline_id: str
    status: str = "pending"  # pending, processing, completed, failed
    progress: float = 0.0
    job_id: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class Item(BaseModel):
    """Item - a content unit (video/article/podcast episode)."""
    item_id: str = Field(..., description="Unique identifier")
    source_type: SourceType = Field(..., description="Source type")
    source_id: str = Field(..., description="Source this item belongs to")

    # Original information
    original_url: str = Field(..., description="Original content URL")
    original_title: str = Field(..., description="Original title")
    original_description: Optional[str] = Field(default=None, description="Original description")
    original_thumbnail: Optional[str] = Field(default=None, description="Original thumbnail URL")
    duration: Optional[float] = Field(default=None, description="Duration in seconds")
    published_at: Optional[datetime] = Field(default=None, description="Original publish date")

    # Status
    status: ItemStatus = Field(default=ItemStatus.DISCOVERED, description="Item status")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Pipeline status summary
    pipelines: Dict[str, PipelineStatus] = Field(
        default_factory=dict,
        description="Pipeline execution status: pipeline_id -> status"
    )

    def update_pipeline_status(
        self,
        pipeline_id: str,
        status: str,
        progress: float = None,
        job_id: str = None,
        error: str = None,
    ) -> None:
        """Update status for a specific pipeline."""
        if pipeline_id not in self.pipelines:
            self.pipelines[pipeline_id] = PipelineStatus(pipeline_id=pipeline_id)

        ps = self.pipelines[pipeline_id]
        ps.status = status
        if progress is not None:
            ps.progress = progress
        if job_id:
            ps.job_id = job_id
        if error:
            ps.error = error
        if status == "processing" and not ps.started_at:
            ps.started_at = datetime.now()
        if status in ("completed", "failed"):
            ps.completed_at = datetime.now()

        self.updated_at = datetime.now()
        self._update_overall_status()

    def _update_overall_status(self) -> None:
        """Update overall item status based on pipeline statuses."""
        if not self.pipelines:
            return

        statuses = [ps.status for ps in self.pipelines.values()]

        if all(s == "completed" for s in statuses):
            self.status = ItemStatus.COMPLETED
        elif any(s == "processing" for s in statuses):
            self.status = ItemStatus.PROCESSING
        elif any(s == "completed" for s in statuses):
            self.status = ItemStatus.PARTIAL
        elif any(s == "failed" for s in statuses):
            self.status = ItemStatus.FAILED
        elif any(s == "pending" for s in statuses):
            self.status = ItemStatus.QUEUED


class ItemCreate(BaseModel):
    """Request model for creating a new item."""
    source_type: SourceType
    source_id: str
    original_url: str
    original_title: str
    original_description: Optional[str] = None
    original_thumbnail: Optional[str] = None
    duration: Optional[float] = None
    published_at: Optional[datetime] = None


class ItemTrigger(BaseModel):
    """Request model for triggering pipelines on an item."""
    pipeline_ids: list[str] = Field(..., description="Pipeline IDs to trigger")
