"""Pipeline configuration API endpoints for SceneMind."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.models.pipeline import (
    PipelineConfig,
    PipelineType,
    PipelineCreate,
    PipelineUpdate,
    TargetType,
)
from app.services.pipeline_manager import PipelineManager


router = APIRouter(prefix="/pipelines", tags=["pipelines"])

# Manager instance - will be set by main.py
pipeline_manager: PipelineManager = None


def set_pipeline_manager(manager: PipelineManager):
    """Set the pipeline manager instance."""
    global pipeline_manager
    pipeline_manager = manager


# ============ CRUD Endpoints ============

@router.post("", response_model=PipelineConfig)
async def create_pipeline(pipeline_create: PipelineCreate):
    """Create a new pipeline configuration."""
    try:
        pipeline = pipeline_manager.create_pipeline(pipeline_create)
        return pipeline
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create pipeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[PipelineConfig])
async def list_pipelines(
    pipeline_type: Optional[PipelineType] = Query(default=None, description="Filter by pipeline type"),
    enabled_only: bool = Query(default=False, description="Only return enabled pipelines"),
    limit: int = Query(default=100, le=500, description="Maximum number of pipelines to return"),
):
    """List all pipeline configurations with optional filtering."""
    return pipeline_manager.list_pipelines(
        pipeline_type=pipeline_type,
        enabled_only=enabled_only,
        limit=limit,
    )


@router.get("/{pipeline_id}", response_model=PipelineConfig)
async def get_pipeline(pipeline_id: str):
    """Get a specific pipeline configuration by ID."""
    pipeline = pipeline_manager.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")
    return pipeline


@router.put("/{pipeline_id}", response_model=PipelineConfig)
async def update_pipeline(pipeline_id: str, pipeline_update: PipelineUpdate):
    """Update an existing pipeline configuration."""
    pipeline = pipeline_manager.update_pipeline(pipeline_id, pipeline_update)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")
    return pipeline


@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    """Delete a pipeline configuration.

    Note: Default pipelines cannot be deleted.
    """
    if not pipeline_manager.delete_pipeline(pipeline_id):
        raise HTTPException(
            status_code=400,
            detail=f"Pipeline '{pipeline_id}' not found or is a default pipeline that cannot be deleted"
        )
    return {"message": f"Pipeline '{pipeline_id}' deleted"}


# ============ Query Endpoints ============

@router.get("/by-type/{pipeline_type}", response_model=List[PipelineConfig])
async def get_pipelines_by_type(pipeline_type: PipelineType):
    """Get all pipelines of a specific type."""
    pipelines_by_type = pipeline_manager.get_pipelines_by_type()
    return pipelines_by_type.get(pipeline_type, [])


@router.get("/by-target/{target_type}", response_model=List[PipelineConfig])
async def get_pipelines_by_target(target_type: TargetType):
    """Get all enabled pipelines targeting a specific platform."""
    return pipeline_manager.get_pipelines_for_target(target_type)


# ============ Statistics Endpoints ============

@router.get("/stats/overview")
async def get_pipelines_stats():
    """Get pipeline statistics."""
    return pipeline_manager.get_stats()
