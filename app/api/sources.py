"""Source management API endpoints for MirrorFlow v2."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.models.source import (
    Source,
    SourceType,
    SourceCreate,
    SourceUpdate,
)
from app.services.source_manager import SourceManager


router = APIRouter(prefix="/sources", tags=["sources"])

# Manager instance - will be set by main.py
source_manager: SourceManager = None


def set_source_manager(manager: SourceManager):
    """Set the source manager instance."""
    global source_manager
    source_manager = manager


# ============ CRUD Endpoints ============

@router.post("", response_model=Source)
async def create_source(source_create: SourceCreate):
    """Create a new content source."""
    try:
        source = source_manager.create_source(source_create)
        return source
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[Source])
async def list_sources(
    source_type: Optional[SourceType] = Query(default=None, description="Filter by source type"),
    enabled_only: bool = Query(default=False, description="Only return enabled sources"),
    limit: int = Query(default=100, le=500, description="Maximum number of sources to return"),
):
    """List all sources with optional filtering."""
    return source_manager.list_sources(
        source_type=source_type,
        enabled_only=enabled_only,
        limit=limit,
    )


@router.get("/{source_id}", response_model=Source)
async def get_source(source_id: str):
    """Get a specific source by ID."""
    source = source_manager.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")
    return source


@router.put("/{source_id}", response_model=Source)
async def update_source(source_id: str, source_update: SourceUpdate):
    """Update an existing source."""
    source = source_manager.update_source(source_id, source_update)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")
    return source


@router.delete("/{source_id}")
async def delete_source(source_id: str):
    """Delete a source."""
    if not source_manager.delete_source(source_id):
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")
    return {"message": f"Source '{source_id}' deleted"}


# ============ Operation Endpoints ============

@router.post("/{source_id}/fetch")
async def trigger_fetch(source_id: str):
    """Trigger an immediate fetch for this source.

    Note: In v2 architecture, fetching is handled by n8n workflows.
    This endpoint updates the last_fetched_at timestamp and can be
    used to trigger n8n webhook if configured.
    """
    source = source_manager.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")

    # Update last_fetched_at
    source_manager.update_last_fetched(source_id)

    return {
        "message": f"Fetch triggered for source '{source_id}'",
        "fetcher": source.fetcher,
    }


@router.get("/{source_id}/items")
async def get_source_items(
    source_id: str,
    limit: int = Query(default=100, le=500),
):
    """Get all items for this source.

    Note: This endpoint requires ItemManager to be imported.
    Implementation will delegate to ItemManager.get_items_by_source().
    """
    source = source_manager.get_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source '{source_id}' not found")

    # Import here to avoid circular imports
    from app.api.items import item_manager

    if item_manager is None:
        raise HTTPException(status_code=500, detail="Item manager not initialized")

    items = item_manager.get_items_by_source(source_id)
    return items[:limit]


# ============ Statistics Endpoints ============

@router.get("/stats/overview")
async def get_sources_stats():
    """Get source statistics."""
    return source_manager.get_stats()


@router.get("/stats/by-type")
async def get_sources_by_type():
    """Get sources grouped by type."""
    result = {}
    for source_type, sources in source_manager.get_sources_by_type().items():
        result[source_type.value] = [s.model_dump(mode="json") for s in sources]
    return result
