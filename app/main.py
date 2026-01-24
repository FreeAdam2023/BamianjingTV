"""MirrorFlow - FastAPI main application."""

import json
from pathlib import Path
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from app import __version__
from app.config import settings
from app.models.job import Job, JobCreate, JobStatus
from app.services.job_manager import JobManager
from app.services.queue import JobQueue, BatchProcessor
from app.services.webhook import WebhookService, job_status_callback
from app.workers.download import DownloadWorker
from app.workers.whisper import WhisperWorker
from app.workers.diarization import DiarizationWorker
from app.workers.translation import TranslationWorker
from app.workers.tts import TTSWorker
from app.workers.mux import MuxWorker
from app.workers.thumbnail import ThumbnailWorker
from app.workers.content import ContentWorker
from app.workers.youtube import YouTubeWorker
from app.api import content_router, youtube_router


# Services
job_manager: JobManager = None
job_queue: JobQueue = None
batch_processor: BatchProcessor = None
webhook_service: WebhookService = None

# Workers
download_worker = DownloadWorker()
whisper_worker = WhisperWorker()
diarization_worker = DiarizationWorker()
translation_worker = TranslationWorker()
tts_worker = TTSWorker()
mux_worker = MuxWorker()
thumbnail_worker = ThumbnailWorker()
content_worker = ContentWorker()
youtube_worker = YouTubeWorker()


async def process_job(job_id: str) -> None:
    """Process a job through the full pipeline."""
    job = job_manager.get_job(job_id)
    if not job:
        return

    job_dir = job.get_job_dir(settings.jobs_dir)
    diarization_segments = None
    translated_transcript = None

    try:
        # ============ Phase 1: Core Pipeline ============

        # Stage 1: Download
        await job_manager.update_status(job, JobStatus.DOWNLOADING, 0.05)

        download_result = await download_worker.download(
            url=job.url,
            output_dir=job_dir,
        )

        job.source_video = download_result["video_path"]
        job.source_audio = download_result["audio_path"]
        job.title = download_result["title"]
        job.duration = download_result["duration"]
        job.channel = download_result["channel"]
        original_description = download_result.get("description", "")
        job_manager.save_job(job)

        # Stage 2: Transcribe
        await job_manager.update_status(job, JobStatus.TRANSCRIBING, 0.15)

        transcript = await whisper_worker.transcribe(
            audio_path=Path(job.source_audio),
        )

        transcript_dir = job_dir / "transcript"
        raw_path = transcript_dir / "raw.json"
        await whisper_worker.save_transcript(transcript, raw_path)
        job.transcript_raw = str(raw_path)
        job_manager.save_job(job)

        # Stage 3: Diarize
        await job_manager.update_status(job, JobStatus.DIARIZING, 0.25)

        diarization_segments = await diarization_worker.diarize(
            audio_path=Path(job.source_audio),
        )

        diarized_transcript = await diarization_worker.merge_with_transcript(
            transcript=transcript,
            diarization_segments=diarization_segments,
        )

        diarized_path = transcript_dir / "diarized.json"
        await diarization_worker.save_diarized_transcript(
            diarized_transcript, diarized_path
        )
        job.transcript_diarized = str(diarized_path)
        job_manager.save_job(job)

        # Stage 4: Translate
        await job_manager.update_status(job, JobStatus.TRANSLATING, 0.35)

        translated_transcript = await translation_worker.translate_transcript(
            transcript=diarized_transcript,
        )

        translation_dir = job_dir / "translation"
        translation_path = translation_dir / "zh.json"
        await translation_worker.save_translation(
            translated_transcript, translation_path
        )
        job.translation = str(translation_path)
        job_manager.save_job(job)

        # Stage 5: TTS
        await job_manager.update_status(job, JobStatus.SYNTHESIZING, 0.45)

        # Extract speaker reference clips
        await tts_worker.extract_speaker_clips(
            audio_path=Path(job.source_audio),
            diarization_segments=diarization_segments,
            output_dir=job_dir / "tts" / "references",
        )

        # Synthesize all segments
        tts_segments = await tts_worker.synthesize_transcript(
            transcript=translated_transcript,
            output_dir=job_dir,
        )

        # Stage 6: Mux
        await job_manager.update_status(job, JobStatus.MUXING, 0.60)

        # Create aligned audio
        aligned_audio_path = job_dir / "tts" / "aligned.wav"
        await mux_worker.create_aligned_audio(
            tts_segments=tts_segments,
            total_duration=job.duration,
            output_path=aligned_audio_path,
        )
        job.tts_audio = str(aligned_audio_path)

        # Mux final video
        output_dir = job_dir / "output"
        output_path = output_dir / "final_video.mp4"
        await mux_worker.mux_video(
            video_path=Path(job.source_video),
            audio_path=aligned_audio_path,
            output_path=output_path,
        )
        job.output_video = str(output_path)
        job_manager.save_job(job)

        # ============ Phase 3: Content Generation ============

        # Stage 7: Generate Content (titles, description, tags)
        if job.generate_content:
            await job_manager.update_status(job, JobStatus.GENERATING_CONTENT, 0.70)

            # Generate summary from translated transcript
            segments_data = [
                {"speaker": seg.speaker, "translation": seg.translation}
                for seg in translated_transcript.segments
            ]
            transcript_summary = await content_worker.generate_transcript_summary(
                segments=segments_data
            )

            # Generate content metadata
            content = await content_worker.generate_content(
                original_title=job.title,
                original_description=original_description,
                transcript_summary=transcript_summary,
                channel_name=job.channel,
                video_duration=job.duration,
            )

            job.title_clickbait = content.title_clickbait
            job.title_safe = content.title_safe
            job.description = content.description
            job.tags = content.tags

            # Generate chapters
            chapters = await content_worker.generate_chapters(
                segments=segments_data,
            )
            job.chapters = chapters

            # Save content to file
            content_path = job_dir / "content" / "metadata.json"
            content_path.parent.mkdir(parents=True, exist_ok=True)
            with open(content_path, "w", encoding="utf-8") as f:
                json.dump({
                    "title_clickbait": content.title_clickbait,
                    "title_safe": content.title_safe,
                    "description": content.description,
                    "tags": content.tags,
                    "keywords": content.keywords,
                    "summary": content.summary,
                    "chapters": chapters,
                }, f, ensure_ascii=False, indent=2)

            job_manager.save_job(job)

        # Stage 8: Generate Thumbnail
        if job.generate_thumbnail:
            await job_manager.update_status(job, JobStatus.GENERATING_THUMBNAIL, 0.80)

            thumbnail_path = job_dir / "output" / "thumbnail.jpg"

            try:
                # Try AI generation
                await thumbnail_worker.generate_from_summary(
                    title=job.title_safe or job.title,
                    summary=content.summary if job.generate_content else "",
                    keywords=content.keywords if job.generate_content else [],
                    output_path=thumbnail_path,
                )
            except Exception as thumb_err:
                logger.warning(f"AI thumbnail failed, extracting from video: {thumb_err}")
                # Fallback to video frame
                await thumbnail_worker.extract_frame_thumbnail(
                    video_path=Path(job.source_video),
                    output_path=thumbnail_path,
                )

            job.thumbnail = str(thumbnail_path)
            job_manager.save_job(job)

        # Stage 9: YouTube Upload (optional)
        if job.auto_upload:
            await job_manager.update_status(job, JobStatus.UPLOADING, 0.90)

            # Prepare description with chapters
            final_description = job.description or ""
            if job.chapters:
                final_description = content_worker.format_description_with_chapters(
                    description=final_description,
                    chapters=job.chapters,
                )

            # Upload to YouTube
            upload_result = await youtube_worker.upload(
                video_path=Path(job.output_video),
                title=job.title_safe or job.title,
                description=final_description,
                tags=job.tags or [],
                privacy_status=job.upload_privacy,
                thumbnail_path=Path(job.thumbnail) if job.thumbnail else None,
            )

            job.youtube_video_id = upload_result["video_id"]
            job.youtube_url = upload_result["url"]
            job_manager.save_job(job)

            logger.info(f"Video uploaded to YouTube: {job.youtube_url}")

        # Done!
        await job_manager.update_status(job, JobStatus.COMPLETED, 1.0)
        logger.info(f"Job {job_id} completed: {job.output_video}")

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

    logger.info(f"Starting MirrorFlow v{__version__}")
    logger.info(f"Jobs directory: {settings.jobs_dir}")

    # Initialize webhook service
    webhook_service = WebhookService()

    # Initialize job manager with webhook callback
    job_manager = JobManager(
        max_retries=3,
        retry_delay=5.0,
        webhook_callback=job_status_callback,
    )

    # Initialize job queue
    job_queue = JobQueue(
        max_concurrent=2,
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
    logger.info("Shutting down MirrorFlow")


app = FastAPI(
    title="MirrorFlow",
    description="Automated video language conversion pipeline",
    version=__version__,
    lifespan=lifespan,
)

# Include API routers
app.include_router(content_router)
app.include_router(youtube_router)


# ============ Request/Response Models ============

class BatchJobCreate(BaseModel):
    """Request model for creating batch jobs."""
    urls: List[str]
    target_language: str = "zh"
    priority: int = 0
    callback_url: Optional[str] = None
    generate_thumbnail: bool = True
    generate_content: bool = True
    auto_upload: bool = False
    upload_privacy: str = "private"


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
        "name": "MirrorFlow",
        "version": __version__,
        "status": "running",
        "features": ["transcription", "diarization", "translation", "tts", "thumbnail", "youtube"],
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
    job = job_manager.create_job(
        url=job_create.url,
        target_language=job_create.target_language,
    )

    # Set Phase 3 options
    job.generate_thumbnail = job_create.generate_thumbnail
    job.generate_content = job_create.generate_content
    job.auto_upload = job_create.auto_upload
    job.upload_privacy = job_create.upload_privacy
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
        job.generate_thumbnail = batch.generate_thumbnail
        job.generate_content = batch.generate_content
        job.auto_upload = batch.auto_upload
        job.upload_privacy = batch.upload_privacy
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
    return job_manager.list_jobs(status=status, limit=limit)


@app.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str):
    """Get a specific job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str, delete_files: bool = True):
    """Delete a job."""
    if not job_manager.delete_job(job_id, delete_files=delete_files):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": f"Job {job_id} deleted"}


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
    }
