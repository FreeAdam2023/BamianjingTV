"""Hardcore Player - FastAPI main application.

Learning video factory: transcription, translation, and bilingual subtitles.
"""

import asyncio
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app import __version__
from app.config import settings
from app.services.job_manager import JobManager
from app.services.queue import JobQueue, BatchProcessor
from app.services.webhook import WebhookService, job_status_callback
from app.services.timeline_manager import TimelineManager
from app.services.source_manager import SourceManager
from app.services.item_manager import ItemManager
from app.services.pipeline_manager import PipelineManager
from app.workers.download import DownloadWorker
from app.workers.whisper import WhisperWorker
from app.workers.diarization import DiarizationWorker
from app.workers.translation import TranslationWorker
from app.workers.export import ExportWorker
from app.workers.youtube import YouTubeWorker
from app.workers.thumbnail import ThumbnailWorker
from app.workers.waveform import WaveformWorker
from app.workers.processor import process_job
from app.api import (
    # Routers
    sources_router,
    items_router,
    pipelines_router,
    overview_router,
    websocket_router,
    timelines_router,
    segments_router,
    export_router,
    media_router,
    jobs_router,
    queue_router,
    cleanup_router,
    channels_router,
    scenemind_router,
    cards_router,
    # Setup functions
    set_source_manager,
    set_item_manager,
    set_pipeline_manager,
    set_overview_managers,
    set_timeline_manager,
    set_export_worker,
    set_youtube_worker,
    set_thumbnail_worker,
    set_waveform_worker,
    set_timelines_frame_capture_worker,
    set_jobs_dir,
    set_job_manager,
    set_job_queue,
    set_webhook_service,
    set_queue_job_queue,
    get_connection_manager,
    set_scenemind_session_manager,
    set_frame_capture_worker,
    # Cards setup functions
    set_card_cache,
    set_card_generator,
    set_ner_worker,
    set_cards_timeline_manager,
)


# Workers (initialized once)
download_worker = DownloadWorker()
whisper_worker = WhisperWorker()
diarization_worker = DiarizationWorker()
translation_worker = TranslationWorker()
export_worker = ExportWorker()
youtube_worker = YouTubeWorker()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(f"Starting Hardcore Player v{__version__}")
    logger.info(f"Jobs directory: {settings.jobs_dir}")
    logger.info(f"Data directory: {settings.data_dir}")

    # Initialize webhook service
    webhook_service = WebhookService()

    # ========== v2: Initialize managers ==========
    source_manager = SourceManager()
    item_manager = ItemManager()
    pipeline_manager = PipelineManager()

    # Set API module managers
    set_source_manager(source_manager)
    set_item_manager(item_manager)
    set_pipeline_manager(pipeline_manager)

    logger.info(f"Initialized v2 managers: {source_manager.get_stats()['total']} sources, "
                f"{item_manager.get_stats()['total']} items, "
                f"{pipeline_manager.get_stats()['total']} pipelines")

    # ========== Hardcore Player: Initialize timeline manager ==========
    timeline_manager = TimelineManager()
    set_timeline_manager(timeline_manager)
    set_export_worker(export_worker)
    set_youtube_worker(youtube_worker)
    thumbnail_worker = ThumbnailWorker()
    set_thumbnail_worker(thumbnail_worker)
    waveform_worker = WaveformWorker()
    set_waveform_worker(waveform_worker)
    set_jobs_dir(settings.jobs_dir)

    logger.info(f"Initialized timeline manager: {timeline_manager.get_stats()['total']} timelines")

    # ========== Frame Capture: Initialize frame capture worker ==========
    from app.workers.frame_capture import FrameCaptureWorker

    frame_capture_worker = FrameCaptureWorker()
    set_timelines_frame_capture_worker(frame_capture_worker)  # For timeline observations

    # ========== SceneMind: Initialize session manager ==========
    from app.services.scenemind import SceneMindSessionManager
    from app.workers.scenemind import FrameCaptureWorker as SceneMindFrameCaptureWorker

    scenemind_session_manager = SceneMindSessionManager()
    set_scenemind_session_manager(scenemind_session_manager)
    scenemind_frame_worker = SceneMindFrameCaptureWorker()  # Keep for backwards compatibility
    set_frame_capture_worker(scenemind_frame_worker)

    logger.info(f"Initialized SceneMind: {scenemind_session_manager.get_stats()['total']} sessions")

    # ========== Cards: Initialize card cache and workers ==========
    from app.services.card_cache import CardCache
    from app.workers.card_generator import CardGeneratorWorker
    from app.workers.ner import NERWorker

    card_cache = CardCache()
    card_generator = CardGeneratorWorker(card_cache=card_cache)
    ner_worker = NERWorker(use_spacy=False)  # Start with rule-based, can enable spaCy later

    set_card_cache(card_cache)
    set_card_generator(card_generator)
    set_ner_worker(ner_worker)
    set_cards_timeline_manager(timeline_manager)

    logger.info(f"Initialized Cards: {card_cache.get_stats()['total_cached']} cached cards")

    # v2: Get WebSocket connection manager
    ws_manager = get_connection_manager()

    # Create WebSocket broadcast callback
    async def ws_broadcast(job_id: str, data: dict):
        await ws_manager.broadcast_job_update(job_id, data)

    # Initialize job manager with webhook callback and item_manager
    job_manager = JobManager(
        max_retries=3,
        retry_delay=5.0,
        webhook_callback=job_status_callback,
        item_manager=item_manager,
        ws_broadcast_callback=ws_broadcast,
    )

    # Set overview managers
    set_overview_managers(source_manager, item_manager, pipeline_manager, job_manager)

    # Create process_job wrapper with all dependencies
    async def process_job_wrapper(job_id: str):
        await process_job(
            job_id=job_id,
            job_manager=job_manager,
            job_queue=job_queue,
            timeline_manager=timeline_manager,
            download_worker=download_worker,
            whisper_worker=whisper_worker,
            diarization_worker=diarization_worker,
            translation_worker=translation_worker,
        )

    # Initialize job queue
    job_queue = JobQueue(
        max_concurrent=settings.max_concurrent_jobs,
        process_func=process_job_wrapper,
    )
    await job_queue.start()

    # Initialize batch processor
    batch_processor = BatchProcessor(job_manager, job_queue)

    # Set job-related dependencies for API routers
    set_job_manager(job_manager)
    set_job_queue(job_queue)
    set_webhook_service(webhook_service)
    set_queue_job_queue(job_queue)

    # Recover incomplete jobs
    recovered = await job_manager.recover_incomplete_jobs(process_job_wrapper)
    if recovered > 0:
        logger.info(f"Recovered {recovered} incomplete jobs")

    # Start background cleanup task if enabled
    cleanup_task = None
    if settings.cleanup_enabled:
        from app.services.cleanup import start_background_cleanup
        cleanup_task = start_background_cleanup(
            jobs_dir=settings.jobs_dir,
            retention_days=settings.cleanup_retention_days,
            videos_only=settings.cleanup_videos_only,
            interval_hours=6,
        )
        logger.info(
            f"Background cleanup enabled: retention={settings.cleanup_retention_days} days, "
            f"videos_only={settings.cleanup_videos_only}"
        )

    yield

    # Cleanup
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    await job_queue.stop()
    await webhook_service.close()
    await card_generator.close()
    logger.info("Shutting down Hardcore Player")


app = FastAPI(
    title="Hardcore Player",
    description="Learning video factory: transcription, translation, and bilingual subtitles",
    version=__version__,
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# v2 API routers
app.include_router(sources_router)
app.include_router(items_router)
app.include_router(pipelines_router)
app.include_router(overview_router)
app.include_router(websocket_router)

# Hardcore Player routers
app.include_router(timelines_router)
app.include_router(segments_router)
app.include_router(export_router)
app.include_router(media_router)
app.include_router(jobs_router)
app.include_router(queue_router)
app.include_router(cleanup_router)
app.include_router(channels_router)
app.include_router(scenemind_router)
app.include_router(cards_router)


# ============ Root Endpoints ============

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Hardcore Player",
        "version": __version__,
        "status": "running",
        "features": ["transcription", "diarization", "translation", "bilingual_subtitles"],
        "v2": {
            "sources": True,
            "items": True,
            "pipelines": True,
            "overview": True,
            "timelines": True,
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    from app.api.queue import _job_queue
    return {
        "status": "healthy",
        "queue": _job_queue.get_stats() if _job_queue else None,
    }


@app.get("/stats")
async def get_stats():
    """Get overall statistics."""
    from app.api.jobs import _job_manager
    from app.api.queue import _job_queue
    from app.api.timelines import _get_manager

    timeline_manager = _get_manager()
    return {
        "jobs": _job_manager.get_stats() if _job_manager else None,
        "queue": _job_queue.get_stats() if _job_queue else None,
        "timelines": timeline_manager.get_stats() if timeline_manager else None,
    }
