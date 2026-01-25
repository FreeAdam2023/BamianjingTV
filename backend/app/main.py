"""Hardcore Player - FastAPI main application.

Learning video factory: transcription, translation, and bilingual subtitles.
"""

import json
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

from app import __version__
from app.config import settings
from app.models.job import Job, JobCreate, JobStatus
from app.services.job_manager import JobManager
from app.services.queue import JobQueue, BatchProcessor
from app.services.webhook import WebhookService, job_status_callback
from app.services.timeline_manager import TimelineManager
from app.workers.download import DownloadWorker
from app.workers.whisper import WhisperWorker
from app.workers.diarization import DiarizationWorker
from app.workers.translation import TranslationWorker
from app.workers.export import ExportWorker
from app.workers.youtube import YouTubeWorker
from app.api import (
    sources_router,
    items_router,
    pipelines_router,
    overview_router,
    websocket_router,
    timelines_router,
    set_source_manager,
    set_item_manager,
    set_pipeline_manager,
    set_overview_managers,
    set_timeline_manager,
    set_export_worker,
    set_youtube_worker,
    set_jobs_dir,
    get_connection_manager,
)
from app.services.source_manager import SourceManager
from app.services.item_manager import ItemManager
from app.services.pipeline_manager import PipelineManager


# Services
job_manager: JobManager = None
job_queue: JobQueue = None
batch_processor: BatchProcessor = None
webhook_service: WebhookService = None

# v2 Services
source_manager: SourceManager = None
item_manager: ItemManager = None
pipeline_manager: PipelineManager = None

# Hardcore Player Services
timeline_manager: TimelineManager = None

# Workers
download_worker = DownloadWorker()
whisper_worker = WhisperWorker()
diarization_worker = DiarizationWorker()
translation_worker = TranslationWorker()
export_worker = ExportWorker()
youtube_worker = YouTubeWorker()


async def process_job(job_id: str) -> None:
    """Process a job through the pipeline.

    Simplified for Hardcore Player (learning video factory):
    1. Download video
    2. Transcribe with Whisper
    3. Diarize speakers
    4. Translate to Chinese
    5. Create Timeline and pause for UI review

    The export stage is triggered separately via /timelines/{id}/export.
    Supports resuming from any stage if files already exist.
    """
    import json
    from app.models.transcript import Transcript, DiarizedTranscript, TranslatedTranscript

    job = job_manager.get_job(job_id)
    if not job:
        return

    job_dir = job.get_job_dir(settings.jobs_dir)
    transcript_dir = job_dir / "transcript"
    translation_dir = job_dir / "translation"

    def check_cancelled() -> bool:
        """Check if job was cancelled and update status if so."""
        fresh_job = job_manager.get_job(job_id)
        if fresh_job and fresh_job.cancel_requested:
            return True
        return False

    def load_json_model(path: Path, model_class):
        """Load a Pydantic model from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            return model_class(**json.load(f))

    try:
        # ============ Stage 1: Download (10%) ============
        await job_manager.update_status(job, JobStatus.DOWNLOADING, 0.10)

        download_result = await download_worker.download(
            url=job.url,
            output_dir=job_dir,
        )

        job.source_video = download_result["video_path"]
        job.source_audio = download_result["audio_path"]
        job.title = download_result["title"]
        job.duration = download_result["duration"]
        job.channel = download_result["channel"]
        job_manager.save_job(job)

        if check_cancelled():
            await job_manager.update_status(job, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} cancelled after download stage")
            return

        # ============ Stage 2: Transcribe (30%) ============
        raw_path = transcript_dir / "raw.json"

        if raw_path.exists():
            logger.info(f"转录文件已存在，跳过转录阶段: {job_id}")
            transcript = load_json_model(raw_path, Transcript)
        else:
            await job_manager.update_status(job, JobStatus.TRANSCRIBING, 0.30)
            transcript = await whisper_worker.transcribe(
                audio_path=Path(job.source_audio),
            )
            await whisper_worker.save_transcript(transcript, raw_path)

        job.transcript_raw = str(raw_path)
        job_manager.save_job(job)

        if check_cancelled():
            await job_manager.update_status(job, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} cancelled after transcription stage")
            return

        # ============ Stage 3: Diarize (50%) ============
        diarized_path = transcript_dir / "diarized.json"

        if diarized_path.exists():
            logger.info(f"说话人识别文件已存在，跳过识别阶段: {job_id}")
            diarized_transcript = load_json_model(diarized_path, DiarizedTranscript)
        elif job.skip_diarization:
            # Skip diarization - convert transcript to diarized format without speakers
            logger.info(f"用户选择跳过说话人识别: {job_id}")
            from app.models.transcript import DiarizedSegment
            diarized_transcript = DiarizedTranscript(
                language=transcript.language,
                num_speakers=1,
                segments=[
                    DiarizedSegment(
                        start=seg.start,
                        end=seg.end,
                        text=seg.text,
                        speaker="SPEAKER_0",
                    )
                    for seg in transcript.segments
                ],
            )
            await diarization_worker.save_diarized_transcript(
                diarized_transcript, diarized_path
            )
        else:
            await job_manager.update_status(job, JobStatus.DIARIZING, 0.50)
            diarization_segments = await diarization_worker.diarize(
                audio_path=Path(job.source_audio),
            )
            diarized_transcript = await diarization_worker.merge_with_transcript(
                transcript=transcript,
                diarization_segments=diarization_segments,
            )
            await diarization_worker.save_diarized_transcript(
                diarized_transcript, diarized_path
            )

        job.transcript_diarized = str(diarized_path)
        job_manager.save_job(job)

        if check_cancelled():
            await job_manager.update_status(job, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} cancelled after diarization stage")
            return

        # ============ Stage 4: Translate (70%) ============
        translation_path = translation_dir / "zh.json"

        if translation_path.exists():
            logger.info(f"翻译文件已存在，跳过翻译阶段: {job_id}")
            translated_transcript = load_json_model(translation_path, TranslatedTranscript)
        else:
            await job_manager.update_status(job, JobStatus.TRANSLATING, 0.70)
            translated_transcript = await translation_worker.translate_transcript(
                transcript=diarized_transcript,
            )
            await translation_worker.save_translation(
                translated_transcript, translation_path
            )

        job.translation = str(translation_path)
        job_manager.save_job(job)

        if check_cancelled():
            await job_manager.update_status(job, JobStatus.CANCELLED)
            logger.info(f"Job {job_id} cancelled after translation stage")
            return

        # ============ Stage 5: Create Timeline (80%) ============
        # Check if timeline already exists
        if job.timeline_id and timeline_manager.get_timeline(job.timeline_id):
            logger.info(f"Timeline已存在，跳过创建: {job.timeline_id}")
            timeline = timeline_manager.get_timeline(job.timeline_id)
        else:
            timeline = timeline_manager.create_from_transcript(
                job_id=job.id,
                source_url=job.url,
                source_title=job.title,
                source_duration=job.duration,
                translated_transcript=translated_transcript,
            )
            job.timeline_id = timeline.timeline_id
            job_manager.save_job(job)

        # ============ PAUSE: Awaiting Review ============
        await job_manager.update_status(job, JobStatus.AWAITING_REVIEW, 0.80)
        logger.info(
            f"Job {job_id} ready for review. "
            f"Timeline: {timeline.timeline_id} ({len(timeline.segments)} segments)"
        )

        # Pipeline pauses here. Export is triggered via /timelines/{id}/export

    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        # Try retry logic
        should_retry = await job_manager.handle_error(
            job, e, stage=job.status.value
        )
        if should_retry:
            # Re-queue the job
            await job_queue.add(job_id, priority=1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global job_manager, job_queue, batch_processor, webhook_service
    global source_manager, item_manager, pipeline_manager, timeline_manager

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
    set_jobs_dir(settings.jobs_dir)

    logger.info(f"Initialized timeline manager: {timeline_manager.get_stats()['total']} timelines")

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
        item_manager=item_manager,  # v2: Enable item status updates
        ws_broadcast_callback=ws_broadcast,  # v2: WebSocket real-time updates
    )

    # Set overview managers
    set_overview_managers(source_manager, item_manager, pipeline_manager, job_manager)

    # Initialize job queue
    job_queue = JobQueue(
        max_concurrent=settings.max_concurrent_jobs,
        process_func=process_job,
    )
    await job_queue.start()

    # Initialize batch processor
    batch_processor = BatchProcessor(job_manager, job_queue)

    # Recover incomplete jobs
    recovered = await job_manager.recover_incomplete_jobs(process_job)
    if recovered > 0:
        logger.info(f"Recovered {recovered} incomplete jobs")

    yield

    # Cleanup
    await job_queue.stop()
    await webhook_service.close()
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


# ============ Request/Response Models ============

class BatchJobCreate(BaseModel):
    """Request model for creating batch jobs."""
    urls: List[str]
    target_language: str = "zh"
    priority: int = 0
    callback_url: Optional[str] = None
    use_traditional_chinese: bool = True


class BatchJobResponse(BaseModel):
    """Response model for batch job creation."""
    job_ids: List[str]
    count: int


class WebhookRegister(BaseModel):
    """Request model for registering a webhook."""
    job_id: str
    callback_url: str


class QueueStats(BaseModel):
    """Queue statistics."""
    running: bool
    max_concurrent: int
    pending: int
    active: int
    active_jobs: List[str]
    processed: int
    failed: int


# ============ Endpoints ============

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
    return {
        "status": "healthy",
        "queue": job_queue.get_stats() if job_queue else None,
    }


# ============ Job Endpoints ============

@app.post("/jobs", response_model=Job)
async def create_job(
    job_create: JobCreate,
    callback_url: Optional[str] = None,
):
    """Create a new video processing job."""
    # Check for duplicate URL
    existing_job = job_manager.get_job_by_url(job_create.url)
    if existing_job:
        raise HTTPException(
            status_code=409,
            detail=f"该视频链接已存在任务 (Job ID: {existing_job.id}, 状态: {existing_job.status.value})"
        )

    job = job_manager.create_job(
        url=job_create.url,
        target_language=job_create.target_language,
        # v2 fields
        source_type=job_create.source_type,
        source_id=job_create.source_id,
        item_id=job_create.item_id,
        pipeline_id=job_create.pipeline_id,
    )

    # Hardcore Player options
    job.use_traditional_chinese = job_create.use_traditional_chinese
    job.skip_diarization = job_create.skip_diarization
    job_manager.save_job(job)

    # Register webhook if provided
    if callback_url:
        webhook_service.register_webhook(job.id, callback_url)

    # Add to queue
    await job_queue.add(job.id)

    logger.info(f"Created job {job.id} for URL: {job.url}")
    return job


@app.post("/jobs/batch", response_model=BatchJobResponse)
async def create_batch_jobs(batch: BatchJobCreate):
    """Create multiple jobs from a list of URLs."""
    job_ids = []

    for url in batch.urls:
        job = job_manager.create_job(
            url=url,
            target_language=batch.target_language,
        )
        job.use_traditional_chinese = batch.use_traditional_chinese
        job_manager.save_job(job)
        job_ids.append(job.id)

    # Add to queue
    await job_queue.add_batch(job_ids, priority=batch.priority)

    # Register webhooks if callback provided
    if batch.callback_url:
        for job_id in job_ids:
            webhook_service.register_webhook(job_id, batch.callback_url)

    return BatchJobResponse(
        job_ids=job_ids,
        count=len(job_ids),
    )


@app.get("/jobs", response_model=List[Job])
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = Query(default=100, le=500),
):
    """List all jobs, optionally filtered by status."""
    jobs = job_manager.list_jobs(status=status, limit=limit)
    # Validate file paths exist before returning
    return [job.validate_file_paths() for job in jobs]


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str):
    """Get a specific job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.validate_file_paths()


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str, delete_files: bool = True):
    """Delete a job."""
    if not job_manager.delete_job(job_id, delete_files=delete_files):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": f"Job {job_id} deleted"}


@app.get("/jobs/{job_id}/video")
async def get_job_video(job_id: str):
    """Download the source video for a job."""
    from fastapi.responses import FileResponse
    from urllib.parse import quote

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if not job.source_video:
        raise HTTPException(status_code=404, detail="视频尚未下载")

    video_path = Path(job.source_video)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="视频文件不存在")

    # Use title for filename, fallback to job_id
    safe_title = (job.title or job_id).replace("/", "_").replace("\\", "_")[:100]
    filename = f"{safe_title}_原版.mp4"
    # URL-encode for Content-Disposition header (RFC 5987)
    filename_encoded = quote(filename)

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"}
    )


@app.get("/jobs/{job_id}/video/export")
async def get_job_export_video(job_id: str):
    """Download the exported video (with subtitles) for a job."""
    from fastapi.responses import FileResponse
    from urllib.parse import quote

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    if not job.output_video:
        raise HTTPException(status_code=404, detail="导出视频尚未生成，请先完成审阅并导出")

    video_path = Path(job.output_video)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="导出视频文件不存在")

    # Use title for filename, fallback to job_id
    safe_title = (job.title or job_id).replace("/", "_").replace("\\", "_")[:100]
    filename = f"{safe_title}_双语字幕.mp4"
    # URL-encode for Content-Disposition header (RFC 5987)
    filename_encoded = quote(filename)

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"}
    )


@app.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    """Retry a failed job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed jobs, current status: {job.status}"
        )

    # Reset and re-queue
    await job_manager.update_status(job, JobStatus.PENDING, progress=0.0)
    await job_queue.add(job_id, priority=1)

    return {"message": f"Job {job_id} queued for retry"}


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job (will stop at next stage boundary)."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")

    # Can only cancel jobs that are in progress
    cancellable_statuses = {
        JobStatus.PENDING,
        JobStatus.DOWNLOADING,
        JobStatus.TRANSCRIBING,
        JobStatus.DIARIZING,
        JobStatus.TRANSLATING,
    }

    if job.status not in cancellable_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"无法取消此状态的任务: {job.status.value}"
        )

    # Set cancel flag - job will check this between stages
    job.cancel_requested = True
    job_manager.save_job(job)

    logger.info(f"Cancel requested for job {job_id}")
    return {"message": f"任务 {job_id} 已标记为取消，将在当前阶段完成后停止"}


# ============ Queue Endpoints ============

@app.get("/queue/stats", response_model=QueueStats)
async def get_queue_stats():
    """Get queue statistics."""
    return job_queue.get_stats()


@app.post("/queue/pause")
async def pause_queue():
    """Pause the job queue (stop accepting new jobs)."""
    await job_queue.stop()
    return {"message": "Queue paused"}


@app.post("/queue/resume")
async def resume_queue():
    """Resume the job queue."""
    await job_queue.start()
    return {"message": "Queue resumed"}


# ============ Webhook Endpoints ============

@app.post("/webhooks/register")
async def register_webhook(webhook: WebhookRegister):
    """Register a webhook callback for a job."""
    job = job_manager.get_job(webhook.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    webhook_service.register_webhook(webhook.job_id, webhook.callback_url)
    return {"message": f"Webhook registered for job {webhook.job_id}"}


@app.delete("/webhooks/{job_id}")
async def unregister_webhook(job_id: str):
    """Unregister webhook for a job."""
    webhook_service.unregister_webhook(job_id)
    return {"message": f"Webhook unregistered for job {job_id}"}


# ============ Stats Endpoints ============

@app.get("/stats")
async def get_stats():
    """Get overall statistics."""
    return {
        "jobs": job_manager.get_stats(),
        "queue": job_queue.get_stats(),
        "timelines": timeline_manager.get_stats() if timeline_manager else None,
    }
