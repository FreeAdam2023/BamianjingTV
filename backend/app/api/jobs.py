"""Job API endpoints.

Handles job creation, listing, status, and video streaming.
"""

import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from loguru import logger

from app.config import settings
from app.models.job import Job, JobCreate, JobStatus, JobMode


router = APIRouter(tags=["jobs"])

# Module-level references (set by main.py during startup)
_job_manager = None
_job_queue = None
_webhook_service = None


def set_job_manager(manager):
    global _job_manager
    _job_manager = manager


def _get_job_manager():
    """Get the job manager instance."""
    return _job_manager


def set_job_queue(queue):
    global _job_queue
    _job_queue = queue


def set_webhook_service(service):
    global _webhook_service
    _webhook_service = service


# ============ Request/Response Models ============

class BatchJobCreate(BaseModel):
    """Request model for creating batch jobs."""
    urls: List[str]
    mode: JobMode = JobMode.LEARNING
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


# ============ Job Endpoints ============

@router.post("/jobs", response_model=Job)
async def create_job(
    job_create: JobCreate,
    callback_url: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
):
    """Create a new video processing job."""
    # Trigger auto-cleanup check in background (if enabled)
    if settings.cleanup_enabled and background_tasks:
        from app.services.cleanup import auto_cleanup_if_needed
        background_tasks.add_task(
            auto_cleanup_if_needed,
            jobs_dir=settings.jobs_dir,
            retention_days=settings.cleanup_retention_days,
            videos_only=settings.cleanup_videos_only,
            enabled=True,
        )

    # Check for duplicate URL
    existing_job = _job_manager.get_job_by_url(job_create.url)
    if existing_job:
        raise HTTPException(
            status_code=409,
            detail=f"A job already exists for this URL (Job ID: {existing_job.id}, status: {existing_job.status.value})"
        )

    job = _job_manager.create_job(
        url=job_create.url,
        target_language=job_create.target_language,
        # v2 fields
        source_type=job_create.source_type,
        source_id=job_create.source_id,
        item_id=job_create.item_id,
        pipeline_id=job_create.pipeline_id,
    )

    # Set mode and mode-specific config
    job.mode = job_create.mode
    job.learning_config = job_create.learning_config
    job.watching_config = job_create.watching_config
    job.dubbing_config = job_create.dubbing_config

    # SceneMind options
    job.use_traditional_chinese = job_create.use_traditional_chinese
    job.skip_diarization = job_create.skip_diarization
    job.whisper_model = job_create.whisper_model
    _job_manager.save_job(job)

    # Register webhook if provided
    if callback_url:
        _webhook_service.register_webhook(job.id, callback_url)

    # Add to queue
    await _job_queue.add(job.id)

    from loguru import logger
    logger.info(f"Created job {job.id} for URL: {job.url}")
    return job


@router.post("/jobs/upload", response_model=Job)
async def create_job_with_upload(
    file: UploadFile = File(...),
    mode: str = Form("learning"),
    target_language: str = Form("zh-TW"),
    skip_diarization: bool = Form(True),
    whisper_model: str = Form("large-v3"),
    title: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
):
    """Create a job with uploaded video file.

    This endpoint accepts a video file upload instead of a URL.
    """
    # Validate file type
    allowed_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}
    original_filename = file.filename or "video.mp4"
    file_ext = Path(original_filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Create job first to get the job ID
    # Use a placeholder URL that will be updated after upload
    placeholder_url = f"upload://{original_filename}"
    job = _job_manager.create_job(
        url=placeholder_url,
        target_language=target_language,
    )
    job_id = job.id

    # Create job directory structure
    job_dir = settings.jobs_dir / job_id
    source_dir = job_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file
    video_filename = f"video{file_ext}"
    video_path = source_dir / video_filename

    max_size = settings.max_upload_size_mb * 1024 * 1024

    try:
        total_size = 0
        with open(video_path, "wb") as buffer:
            while chunk := await file.read(8 * 1024 * 1024):  # 8MB chunks
                total_size += len(chunk)
                if total_size > max_size:
                    buffer.close()
                    shutil.rmtree(job_dir, ignore_errors=True)
                    _job_manager.delete_job(job_id, delete_files=False)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size: {settings.max_upload_size_mb}MB"
                    )
                buffer.write(chunk)

        logger.info(f"Uploaded video for job {job_id}: {video_path} ({total_size / 1024 / 1024:.1f}MB)")

    except HTTPException:
        raise
    except Exception as e:
        shutil.rmtree(job_dir, ignore_errors=True)
        _job_manager.delete_job(job_id, delete_files=False)
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    # Update job with local file path
    job.url = f"file://{video_path}"

    # Set mode and options
    job.mode = JobMode(mode)
    job.skip_diarization = skip_diarization
    job.whisper_model = whisper_model
    job.use_traditional_chinese = target_language.startswith("zh-TW")

    # Set title from form or filename
    job.title = title or Path(original_filename).stem

    # Mark video as already downloaded
    job.source_video = str(video_path)

    _job_manager.save_job(job)

    # Add to queue
    await _job_queue.add(job_id)

    logger.info(f"Created upload job {job_id} for file: {original_filename}")
    return job


@router.post("/jobs/batch", response_model=BatchJobResponse)
async def create_batch_jobs(batch: BatchJobCreate):
    """Create multiple jobs from a list of URLs."""
    job_ids = []

    for url in batch.urls:
        job = _job_manager.create_job(
            url=url,
            target_language=batch.target_language,
        )
        job.mode = batch.mode
        job.use_traditional_chinese = batch.use_traditional_chinese
        _job_manager.save_job(job)
        job_ids.append(job.id)

    # Add to queue
    await _job_queue.add_batch(job_ids, priority=batch.priority)

    # Register webhooks if callback provided
    if batch.callback_url:
        for job_id in job_ids:
            _webhook_service.register_webhook(job_id, batch.callback_url)

    return BatchJobResponse(
        job_ids=job_ids,
        count=len(job_ids),
    )


@router.get("/jobs", response_model=List[Job])
async def list_jobs(
    status: Optional[JobStatus] = None,
    limit: int = Query(default=100, le=500),
):
    """List all jobs, optionally filtered by status."""
    jobs = _job_manager.list_jobs(status=status, limit=limit)
    # Validate file paths exist before returning
    return [job.validate_file_paths() for job in jobs]


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str):
    """Get a specific job."""
    job = _job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.validate_file_paths()


class JobUpdate(BaseModel):
    """Request body for updating job fields."""
    title: Optional[str] = None


@router.patch("/jobs/{job_id}", response_model=Job)
async def update_job(job_id: str, update: JobUpdate):
    """Update job fields (currently supports title)."""
    job = _job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if update.title is not None:
        job.title = update.title.strip() or job.title

    _job_manager.save_job(job)
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, delete_files: bool = True):
    """Delete a job and its associated timeline."""
    from app.api.timelines import _get_manager as _get_timeline_manager

    # First, delete associated timeline if it exists
    timeline_manager = _get_timeline_manager()
    if timeline_manager:
        timeline = timeline_manager.get_timeline_by_job(job_id)
        if timeline:
            timeline_manager.delete_timeline(timeline.timeline_id)

    # Then delete the job
    if not _job_manager.delete_job(job_id, delete_files=delete_files):
        raise HTTPException(status_code=404, detail="Job not found")

    return {"message": f"Job {job_id} deleted"}


@router.get("/jobs/{job_id}/video")
async def get_job_video(job_id: str):
    """Stream the source video for a job (for playback in video element)."""
    job = _job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.source_video:
        raise HTTPException(status_code=404, detail="Video not downloaded yet")

    video_path = Path(job.source_video)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    # Return video for inline playback (no Content-Disposition: attachment)
    return FileResponse(
        video_path,
        media_type="video/mp4",
    )


@router.get("/jobs/{job_id}/video/export")
async def get_job_export_video(job_id: str):
    """Download the exported video (with subtitles) for a job."""
    job = _job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.output_video:
        raise HTTPException(status_code=404, detail="Exported video not generated. Please complete review and export first")

    video_path = Path(job.output_video)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Exported video file not found")

    # Use title for filename, fallback to job_id
    safe_title = (job.title or job_id).replace("/", "_").replace("\\", "_")[:100]
    filename = f"{safe_title}_bilingual.mp4"
    # URL-encode for Content-Disposition header (RFC 5987)
    filename_encoded = quote(filename)

    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}"}
    )


@router.get("/jobs/{job_id}/video/preview/full")
async def preview_export_full(job_id: str):
    """Stream the full exported video (with subtitles) for preview.

    Unlike /video/export, this streams inline for video player preview.
    """
    job = _job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.output_video:
        raise HTTPException(status_code=404, detail="Exported video not generated. Complete export first.")

    video_path = Path(job.output_video)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Exported video file not found")

    return FileResponse(
        video_path,
        media_type="video/mp4",
    )


@router.get("/jobs/{job_id}/video/preview/essence")
async def preview_export_essence(job_id: str):
    """Stream the essence exported video (KEEP segments only) for preview."""
    job = _job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Look for essence video in output directory
    job_dir = settings.jobs_dir / job_id / "output"
    essence_path = job_dir / "essence.mp4"

    if not essence_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Essence video not generated. Export with 'essence' or 'both' profile."
        )

    return FileResponse(
        essence_path,
        media_type="video/mp4",
    )


@router.get("/jobs/{job_id}/thumbnail/{filename}")
async def get_thumbnail(job_id: str, filename: str):
    """Get generated thumbnail image for a job."""
    job_dir = settings.jobs_dir / job_id
    thumbnail_path = job_dir / "output" / filename

    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    return FileResponse(
        thumbnail_path,
        media_type="image/png",
        filename=filename,
    )


@router.get("/jobs/{job_id}/thumbnail/candidates/{filename}")
async def get_thumbnail_candidate(job_id: str, filename: str):
    """Get a thumbnail candidate screenshot image."""
    job_dir = settings.jobs_dir / job_id
    candidate_path = job_dir / "output" / "thumbnail_candidates" / filename

    if not candidate_path.exists():
        raise HTTPException(status_code=404, detail="Candidate not found")

    return FileResponse(
        candidate_path,
        media_type="image/jpeg",
        filename=filename,
    )


@router.get("/jobs/{job_id}/cover")
async def get_cover_frame(job_id: str):
    """Get the captured cover frame image for a job."""
    job_dir = settings.jobs_dir / job_id
    cover_path = job_dir / "output" / "cover_frame.jpg"

    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover frame not found")

    return FileResponse(
        cover_path,
        media_type="image/jpeg",
        filename="cover_frame.jpg",
    )


@router.get("/jobs/{job_id}/stills")
async def list_stills(job_id: str):
    """List rendered card/subtitle still PNGs for a job."""
    stills_dir = settings.jobs_dir / job_id / "output" / "stills"
    if not stills_dir.exists():
        raise HTTPException(status_code=404, detail="Stills directory not found")

    pngs = sorted(
        [f.name for f in stills_dir.iterdir() if f.suffix == ".png"],
    )
    # Load cards_input.json for metadata if available
    cards_meta = {}
    cards_file = stills_dir / "cards_input.json"
    if cards_file.exists():
        import json
        try:
            cards = json.loads(cards_file.read_text(encoding="utf-8"))
            for c in cards:
                cards_meta[c["id"]] = {"card_type": c.get("card_type"), "card_data_keys": list(c.get("card_data", {}).keys())}
        except Exception:
            pass

    items = []
    for name in pngs:
        card_id = name.replace(".png", "")
        size = (stills_dir / name).stat().st_size
        meta = cards_meta.get(card_id)
        items.append({
            "filename": name,
            "card_id": card_id,
            "size": size,
            "is_subtitle": name.startswith("sub_"),
            "card_type": meta["card_type"] if meta else None,
        })
    return {"job_id": job_id, "count": len(items), "stills": items}


@router.get("/jobs/{job_id}/stills/{filename}")
async def get_still(job_id: str, filename: str):
    """Get a rendered still PNG for a job."""
    if not filename.endswith(".png"):
        raise HTTPException(status_code=400, detail="Only .png files allowed")
    still_path = settings.jobs_dir / job_id / "output" / "stills" / filename
    if not still_path.exists():
        raise HTTPException(status_code=404, detail="Still not found")
    return FileResponse(still_path, media_type="image/png")


@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    """Retry a failed job."""
    job = _job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Can only retry failed jobs, current status: {job.status}"
        )

    # Reset and re-queue
    await _job_manager.update_status(job, JobStatus.PENDING, progress=0.0)
    await _job_queue.add(job_id, priority=1)

    return {"message": f"Job {job_id} queued for retry"}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job (will stop at next stage boundary)."""
    from loguru import logger

    job = _job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

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
            detail=f"Cannot cancel job in status: {job.status.value}"
        )

    # Set cancel flag - job will check this between stages
    job.cancel_requested = True
    _job_manager.save_job(job)

    logger.info(f"Cancel requested for job {job_id}")
    return {"message": f"Job {job_id} marked for cancellation, will stop after current stage completes"}


# ============ Webhook Endpoints ============

@router.post("/webhooks/register")
async def register_webhook(webhook: WebhookRegister):
    """Register a webhook callback for a job."""
    job = _job_manager.get_job(webhook.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    _webhook_service.register_webhook(webhook.job_id, webhook.callback_url)
    return {"message": f"Webhook registered for job {webhook.job_id}"}


@router.delete("/webhooks/{job_id}")
async def unregister_webhook(job_id: str):
    """Unregister webhook for a job."""
    _webhook_service.unregister_webhook(job_id)
    return {"message": f"Webhook unregistered for job {job_id}"}
