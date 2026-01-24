"""Item management API endpoints for MirrorFlow v2."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from app.models.source import SourceType
from app.models.item import Item, ItemStatus, ItemCreate, ItemTrigger
from app.services.item_manager import ItemManager


router = APIRouter(prefix="/items", tags=["items"])

# Manager instance - will be set by main.py
item_manager: ItemManager = None


def set_item_manager(manager: ItemManager):
    """Set the item manager instance."""
    global item_manager
    item_manager = manager


# ============ Response Models ============

class ItemResponse(BaseModel):
    """Response model for item creation."""
    item: Item
    is_new: bool


class TriggerResponse(BaseModel):
    """Response model for pipeline trigger."""
    item_id: str
    triggered_pipelines: List[str]
    job_ids: List[str]


# ============ CRUD Endpoints ============

@router.post("", response_model=ItemResponse)
async def create_item(item_create: ItemCreate):
    """Create a new content item.

    If an item with the same URL already exists for the source,
    returns the existing item with is_new=False.
    """
    try:
        # Check if item already exists
        existing = item_manager.get_item_by_url(
            item_create.source_id,
            item_create.original_url
        )

        if existing:
            return ItemResponse(item=existing, is_new=False)

        item = item_manager.create_item(item_create)
        return ItemResponse(item=item, is_new=True)

    except Exception as e:
        logger.error(f"Failed to create item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[Item])
async def list_items(
    source_type: Optional[SourceType] = Query(default=None, description="Filter by source type"),
    source_id: Optional[str] = Query(default=None, description="Filter by source ID"),
    status: Optional[ItemStatus] = Query(default=None, description="Filter by item status"),
    limit: int = Query(default=100, le=500, description="Maximum number of items to return"),
    offset: int = Query(default=0, ge=0, description="Number of items to skip"),
):
    """List items with optional filtering."""
    return item_manager.list_items(
        source_type=source_type,
        source_id=source_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get("/recent", response_model=List[Item])
async def get_recent_items(
    hours: int = Query(default=24, ge=1, le=168, description="Hours to look back"),
):
    """Get items created within the last N hours."""
    return item_manager.get_recent_items(hours=hours)


@router.get("/{item_id}", response_model=Item)
async def get_item(item_id: str):
    """Get a specific item by ID with all pipeline statuses."""
    item = item_manager.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")
    return item


@router.delete("/{item_id}")
async def delete_item(item_id: str):
    """Delete an item."""
    if not item_manager.delete_item(item_id):
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")
    return {"message": f"Item '{item_id}' deleted"}


# ============ Pipeline Operations ============

@router.post("/{item_id}/trigger", response_model=TriggerResponse)
async def trigger_pipelines(item_id: str, trigger: ItemTrigger):
    """Trigger specified pipelines for this item.

    Creates jobs for each pipeline and returns the job IDs.
    """
    item = item_manager.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")

    # Import here to avoid circular imports
    from app.api.pipelines import pipeline_manager
    from app.services.job_manager import JobManager

    if pipeline_manager is None:
        raise HTTPException(status_code=500, detail="Pipeline manager not initialized")

    triggered = []
    job_ids = []

    for pipeline_id in trigger.pipeline_ids:
        pipeline = pipeline_manager.get_pipeline(pipeline_id)
        if not pipeline:
            logger.warning(f"Pipeline '{pipeline_id}' not found, skipping")
            continue

        if not pipeline.enabled:
            logger.warning(f"Pipeline '{pipeline_id}' is disabled, skipping")
            continue

        # Update item pipeline status to pending
        item_manager.update_pipeline_status(
            item_id=item_id,
            pipeline_id=pipeline_id,
            status="pending",
        )

        triggered.append(pipeline_id)
        # Note: Actual job creation would happen here
        # For now, we just track that the pipeline was triggered
        # The actual job creation will be handled by main.py's job_queue

    return TriggerResponse(
        item_id=item_id,
        triggered_pipelines=triggered,
        job_ids=job_ids,
    )


@router.get("/{item_id}/pipelines")
async def get_item_pipelines(item_id: str):
    """Get all pipeline execution statuses for this item."""
    item = item_manager.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")

    return {
        "item_id": item_id,
        "status": item.status.value,
        "pipelines": {
            pid: ps.model_dump(mode="json")
            for pid, ps in item.pipelines.items()
        }
    }


@router.get("/{item_id}/fanout")
async def get_fanout_status(item_id: str):
    """Get fan-out distribution status for this item.

    Shows the status of all pipelines this item has been distributed to.
    """
    fanout = item_manager.get_fanout_status(item_id)
    if fanout is None:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")

    # Enrich with pipeline display names
    from app.api.pipelines import pipeline_manager

    if pipeline_manager:
        for pipeline_id, status in fanout["pipelines"].items():
            pipeline = pipeline_manager.get_pipeline(pipeline_id)
            if pipeline:
                status["display_name"] = pipeline.display_name
                status["target"] = pipeline.target.display_name

    return fanout


# ============ Statistics Endpoints ============

@router.get("/stats/overview")
async def get_items_stats():
    """Get item statistics."""
    return item_manager.get_stats()


@router.get("/stats/by-source-type")
async def get_items_by_source_type():
    """Get overview statistics grouped by source type."""
    return item_manager.get_overview_by_source_type()


# ============ Quick Actions ============

@router.post("/{item_id}/process")
async def process_item(item_id: str):
    """Quick action: Create a job to process this item.

    This is a convenience endpoint for the manual review workflow.
    It creates a job using the item's original URL.
    """
    item = item_manager.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")

    # Import job manager
    from app.api.jobs import job_manager, job_queue

    if job_manager is None:
        raise HTTPException(status_code=500, detail="Job manager not initialized")

    # Create job from item URL
    job = job_manager.create_job(url=item.original_url)

    # Queue the job
    if job_queue:
        await job_queue.add_job(job.job_id)

    # Update item status
    item_manager.update_item_status(item_id, ItemStatus.QUEUED)

    logger.info(f"Created job {job.job_id} for item {item_id}")

    return {
        "item_id": item_id,
        "job_id": job.job_id,
        "status": "queued",
        "message": f"Job created for '{item.original_title}'"
    }
