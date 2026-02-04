"""Overview and aggregation API endpoints for SceneMind.

These endpoints provide high-level views for dashboards and monitoring.
"""

from typing import Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.models.source import SourceType
from app.services.source_manager import SourceManager
from app.services.item_manager import ItemManager
from app.services.pipeline_manager import PipelineManager
from app.services.job_manager import JobManager


router = APIRouter(prefix="/overview", tags=["overview"])

# Manager instances - will be set by main.py
source_manager: SourceManager = None
item_manager: ItemManager = None
pipeline_manager: PipelineManager = None
job_manager: JobManager = None


def set_managers(
    sm: SourceManager,
    im: ItemManager,
    pm: PipelineManager,
    jm: JobManager,
):
    """Set the manager instances."""
    global source_manager, item_manager, pipeline_manager, job_manager
    source_manager = sm
    item_manager = im
    pipeline_manager = pm
    job_manager = jm


# ============ Response Models ============

class SourceTypeOverview(BaseModel):
    """Overview for a single source type."""
    source_count: int
    item_count: int
    new_items_24h: int
    active_pipelines: int


class SystemOverview(BaseModel):
    """System-wide overview."""
    total_sources: int
    total_items: int
    total_pipelines: int
    active_jobs: int
    by_source_type: Dict[str, SourceTypeOverview]


# ============ Overview Endpoints ============

@router.get("", response_model=SystemOverview)
async def get_overview():
    """Get system-wide overview statistics.

    Returns aggregated statistics grouped by source type,
    suitable for rendering a dashboard view.
    """
    source_stats = source_manager.get_stats()
    item_stats = item_manager.get_stats()
    pipeline_stats = pipeline_manager.get_stats()

    # Get item overview by source type
    item_overview = item_manager.get_overview_by_source_type()

    # Convert to response format
    by_source_type = {}
    for source_type in SourceType:
        type_key = source_type.value
        if type_key in item_overview:
            by_source_type[type_key] = SourceTypeOverview(
                source_count=item_overview[type_key].get("source_count", 0),
                item_count=item_overview[type_key].get("item_count", 0),
                new_items_24h=item_overview[type_key].get("new_items_24h", 0),
                active_pipelines=item_overview[type_key].get("active_pipelines", 0),
            )
        elif type_key in source_stats.get("by_type", {}):
            # Source exists but no items yet
            by_source_type[type_key] = SourceTypeOverview(
                source_count=source_stats["by_type"][type_key],
                item_count=0,
                new_items_24h=0,
                active_pipelines=0,
            )

    return SystemOverview(
        total_sources=source_stats["total"],
        total_items=item_stats["total"],
        total_pipelines=pipeline_stats["total"],
        active_jobs=job_manager.get_active_jobs_count(),
        by_source_type=by_source_type,
    )


# ============ Aggregation Endpoints (must come BEFORE /{source_type}) ============

@router.get("/stats/combined")
async def get_combined_stats():
    """Get combined statistics from all managers."""
    return {
        "sources": source_manager.get_stats(),
        "items": item_manager.get_stats(),
        "pipelines": pipeline_manager.get_stats(),
        "jobs": job_manager.get_stats(),
    }


@router.get("/activity/recent")
async def get_recent_activity(hours: int = 24):
    """Get recent activity summary.

    Shows items and jobs created/updated in the last N hours.
    """
    recent_items = item_manager.get_recent_items(hours)

    # Count items by status
    items_by_status = {}
    for item in recent_items:
        status = item.status.value
        items_by_status[status] = items_by_status.get(status, 0) + 1

    return {
        "hours": hours,
        "new_items": len(recent_items),
        "items_by_status": items_by_status,
        "items": [
            {
                "item_id": item.item_id,
                "source_id": item.source_id,
                "title": item.original_title[:50] + "..." if len(item.original_title) > 50 else item.original_title,
                "status": item.status.value,
                "created_at": item.created_at.isoformat(),
            }
            for item in recent_items[:20]  # Last 20 items
        ]
    }


@router.get("/health")
async def get_system_health():
    """Get system health status.

    Checks if all managers are initialized and operational.
    """
    health = {
        "status": "healthy",
        "components": {
            "source_manager": source_manager is not None,
            "item_manager": item_manager is not None,
            "pipeline_manager": pipeline_manager is not None,
            "job_manager": job_manager is not None,
        }
    }

    if not all(health["components"].values()):
        health["status"] = "degraded"

    return health


# ============ Source Type Overview (must come AFTER specific routes) ============

@router.get("/{source_type}")
async def get_source_type_overview(source_type: SourceType):
    """Get detailed overview for a specific source type.

    Returns all sources of this type with their items and pipeline statuses.
    """
    # Get sources of this type
    sources = source_manager.list_sources(source_type=source_type)

    if not sources:
        return {
            "source_type": source_type.value,
            "sources": [],
            "summary": {
                "source_count": 0,
                "item_count": 0,
                "new_items_24h": 0,
            }
        }

    # Build detailed view
    source_details = []
    total_items = 0
    total_new_24h = 0

    for source in sources:
        items = item_manager.get_items_by_source(source.source_id)
        recent_items = [i for i in item_manager.get_recent_items(24) if i.source_id == source.source_id]

        source_details.append({
            "source_id": source.source_id,
            "display_name": source.display_name,
            "enabled": source.enabled,
            "fetcher": source.fetcher,
            "item_count": len(items),
            "new_items_24h": len(recent_items),
            "last_fetched_at": source.last_fetched_at.isoformat() if source.last_fetched_at else None,
        })

        total_items += len(items)
        total_new_24h += len(recent_items)

    return {
        "source_type": source_type.value,
        "sources": source_details,
        "summary": {
            "source_count": len(sources),
            "item_count": total_items,
            "new_items_24h": total_new_24h,
        }
    }
