"""API routers for Hardcore Player."""

from .sources import router as sources_router, set_source_manager
from .items import router as items_router, set_item_manager
from .pipelines import router as pipelines_router, set_pipeline_manager
from .overview import router as overview_router, set_managers as set_overview_managers
from .websocket import router as websocket_router, get_connection_manager
from .timelines import (
    router as timelines_router,
    set_timeline_manager,
    set_export_worker,
    set_youtube_worker,
    set_thumbnail_worker,
    set_waveform_worker,
    set_jobs_dir,
)
from .jobs import (
    router as jobs_router,
    set_job_manager,
    set_job_queue,
    set_webhook_service,
)
from .queue import router as queue_router, set_job_queue as set_queue_job_queue
from .cleanup import router as cleanup_router
from .segments import router as segments_router
from .export import router as export_router
from .media import router as media_router
from .channels import router as channels_router

__all__ = [
    # v2 Routers
    "sources_router",
    "items_router",
    "pipelines_router",
    "overview_router",
    "websocket_router",
    # Hardcore Player Routers
    "timelines_router",
    "segments_router",
    "export_router",
    "media_router",
    "jobs_router",
    "queue_router",
    "cleanup_router",
    "channels_router",
    # v2 Setup functions
    "set_source_manager",
    "set_item_manager",
    "set_pipeline_manager",
    "set_overview_managers",
    "get_connection_manager",
    # Hardcore Player Setup functions
    "set_timeline_manager",
    "set_export_worker",
    "set_youtube_worker",
    "set_thumbnail_worker",
    "set_waveform_worker",
    "set_jobs_dir",
    # Job/Queue Setup functions
    "set_job_manager",
    "set_job_queue",
    "set_webhook_service",
    "set_queue_job_queue",
]
