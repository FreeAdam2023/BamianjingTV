"""API routers for SceneMind."""

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
    set_frame_capture_worker as set_timelines_frame_capture_worker,
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
from .scenemind import (
    router as scenemind_router,
    set_session_manager as set_scenemind_session_manager,
    set_frame_capture_worker,
)
from .cards import (
    router as cards_router,
    set_card_cache,
    set_card_generator,
    set_ner_worker,
    set_timeline_manager as set_cards_timeline_manager,
)
from .memory_books import (
    router as memory_books_router,
    set_memory_book_manager,
    set_anki_export_worker,
)
from .dubbing import (
    router as dubbing_router,
    set_timeline_manager as set_dubbing_timeline_manager,
    set_audio_separation_worker,
    set_voice_clone_worker,
    set_audio_mixer_worker,
    set_lip_sync_worker,
)

__all__ = [
    # v2 Routers
    "sources_router",
    "items_router",
    "pipelines_router",
    "overview_router",
    "websocket_router",
    # SceneMind Routers
    "timelines_router",
    "segments_router",
    "export_router",
    "media_router",
    "jobs_router",
    "queue_router",
    "cleanup_router",
    "channels_router",
    # SceneMind Router
    "scenemind_router",
    # Cards Router
    "cards_router",
    # v2 Setup functions
    "set_source_manager",
    "set_item_manager",
    "set_pipeline_manager",
    "set_overview_managers",
    "get_connection_manager",
    # SceneMind Setup functions
    "set_timeline_manager",
    "set_export_worker",
    "set_youtube_worker",
    "set_thumbnail_worker",
    "set_waveform_worker",
    "set_timelines_frame_capture_worker",
    "set_jobs_dir",
    # Job/Queue Setup functions
    "set_job_manager",
    "set_job_queue",
    "set_webhook_service",
    "set_queue_job_queue",
    # SceneMind Setup functions
    "set_scenemind_session_manager",
    "set_frame_capture_worker",
    # Cards Setup functions
    "set_card_cache",
    "set_card_generator",
    "set_ner_worker",
    "set_cards_timeline_manager",
    # Memory Books Router and Setup functions
    "memory_books_router",
    "set_memory_book_manager",
    "set_anki_export_worker",
    # Dubbing Router and Setup functions
    "dubbing_router",
    "set_dubbing_timeline_manager",
    "set_audio_separation_worker",
    "set_voice_clone_worker",
    "set_audio_mixer_worker",
    "set_lip_sync_worker",
]
