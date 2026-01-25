"""Job manager with error recovery and retry logic."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Awaitable, TYPE_CHECKING
from loguru import logger

from app.config import settings
from app.models.job import Job, JobStatus
from app.models.source import SourceType

if TYPE_CHECKING:
    from app.services.item_manager import ItemManager


class JobManager:
    """Manages job lifecycle with error recovery and retry support."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        webhook_callback: Optional[Callable[[Job], Awaitable[None]]] = None,
        item_manager: Optional["ItemManager"] = None,
        ws_broadcast_callback: Optional[Callable[[str, dict], Awaitable[None]]] = None,
    ):
        self.jobs: Dict[str, Job] = {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.webhook_callback = webhook_callback
        self.item_manager = item_manager  # v2: For updating item pipeline status
        self.ws_broadcast_callback = ws_broadcast_callback  # v2: WebSocket broadcast
        self._retry_counts: Dict[str, int] = {}
        self._load_existing_jobs()

    def _load_existing_jobs(self) -> None:
        """Load existing jobs from disk on startup."""
        jobs_dir = settings.jobs_dir
        if not jobs_dir.exists():
            return

        for job_dir in jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue

            meta_path = job_dir / "meta.json"
            if not meta_path.exists():
                continue

            try:
                with open(meta_path) as f:
                    data = json.load(f)
                job = Job(**data)
                self.jobs[job.id] = job

                # Check for incomplete jobs that need recovery
                if job.status not in (JobStatus.COMPLETED, JobStatus.FAILED):
                    logger.warning(
                        f"Found incomplete job {job.id} in status {job.status}"
                    )

            except Exception as e:
                logger.error(f"Failed to load job from {meta_path}: {e}")

        logger.info(f"Loaded {len(self.jobs)} existing jobs")

    def save_job(self, job: Job) -> None:
        """Save job state to disk."""
        job_dir = job.get_job_dir(settings.jobs_dir)
        job_dir.mkdir(parents=True, exist_ok=True)
        meta_path = job_dir / "meta.json"

        with open(meta_path, "w") as f:
            json.dump(job.model_dump(mode="json"), f, indent=2, default=str)

    def create_job(
        self,
        url: str,
        target_language: str = "zh",
        source_type: Optional[SourceType] = None,
        source_id: Optional[str] = None,
        item_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
    ) -> Job:
        """Create a new job.

        Args:
            url: Video URL
            target_language: Target language code
            source_type: v2 - Source type
            source_id: v2 - Source ID
            item_id: v2 - Item ID
            pipeline_id: v2 - Pipeline ID
        """
        job = Job(
            url=url,
            target_language=target_language,
            source_type=source_type,
            source_id=source_id,
            item_id=item_id,
            pipeline_id=pipeline_id,
        )
        self.jobs[job.id] = job
        self._retry_counts[job.id] = 0
        self.save_job(job)
        logger.info(f"Created job {job.id} for URL: {url}")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        source_type: Optional[SourceType] = None,
        source_id: Optional[str] = None,
        item_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Job]:
        """List jobs, optionally filtered by status and v2 fields."""
        jobs = list(self.jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        # v2 filters
        if source_type:
            jobs = [j for j in jobs if j.source_type == source_type]

        if source_id:
            jobs = [j for j in jobs if j.source_id == source_id]

        if item_id:
            jobs = [j for j in jobs if j.item_id == item_id]

        if pipeline_id:
            jobs = [j for j in jobs if j.pipeline_id == pipeline_id]

        # Sort by creation time, newest first
        jobs.sort(key=lambda j: j.created_at, reverse=True)

        return jobs[:limit]

    def delete_job(self, job_id: str, delete_files: bool = True) -> bool:
        """Delete a job."""
        job = self.jobs.pop(job_id, None)
        if not job:
            return False

        if delete_files:
            job_dir = job.get_job_dir(settings.jobs_dir)
            if job_dir.exists():
                import shutil
                shutil.rmtree(job_dir)

        self._retry_counts.pop(job_id, None)
        logger.info(f"Deleted job {job_id}")
        return True

    async def update_status(
        self,
        job: Job,
        status: JobStatus,
        progress: float = None,
        error: str = None,
    ) -> None:
        """Update job status and trigger webhook if configured."""
        job.status = status
        if progress is not None:
            job.progress = progress
        if error:
            job.error = error
        job.updated_at = datetime.now()

        self.save_job(job)

        # v2: Update item pipeline status if item_manager is available
        if self.item_manager and job.item_id and job.pipeline_id:
            pipeline_status = self._map_job_status_to_pipeline_status(status)
            try:
                self.item_manager.update_pipeline_status(
                    item_id=job.item_id,
                    pipeline_id=job.pipeline_id,
                    status=pipeline_status,
                    progress=progress,
                    job_id=job.id,
                    error=error,
                )
            except Exception as e:
                logger.error(f"Failed to update item pipeline status: {e}")

        # Trigger webhook callback
        if self.webhook_callback:
            try:
                await self.webhook_callback(job)
            except Exception as e:
                logger.error(f"Webhook callback failed for job {job.id}: {e}")

        # v2: Broadcast via WebSocket
        if self.ws_broadcast_callback:
            try:
                await self.ws_broadcast_callback(job.id, {
                    "job_id": job.id,
                    "status": job.status.value,
                    "progress": job.progress,
                    "error": job.error,
                    "title": job.title,
                    "item_id": job.item_id,
                    "source_id": job.source_id,
                    "pipeline_id": job.pipeline_id,
                })
            except Exception as e:
                logger.error(f"WebSocket broadcast failed for job {job.id}: {e}")

    @staticmethod
    def _map_job_status_to_pipeline_status(job_status: JobStatus) -> str:
        """Map JobStatus to pipeline status string."""
        if job_status == JobStatus.PENDING:
            return "pending"
        elif job_status == JobStatus.COMPLETED:
            return "completed"
        elif job_status == JobStatus.FAILED:
            return "failed"
        else:
            return "processing"

    async def handle_error(
        self,
        job: Job,
        error: Exception,
        stage: str,
    ) -> bool:
        """
        Handle job error with retry logic.

        Returns:
            True if job should be retried, False if max retries exceeded
        """
        retry_count = self._retry_counts.get(job.id, 0)
        error_msg = f"Stage '{stage}' failed: {str(error)}"

        if retry_count < self.max_retries:
            self._retry_counts[job.id] = retry_count + 1
            logger.warning(
                f"Job {job.id} error (attempt {retry_count + 1}/{self.max_retries}): "
                f"{error_msg}"
            )

            # Wait before retry
            await asyncio.sleep(self.retry_delay * (retry_count + 1))
            return True

        # Max retries exceeded
        logger.error(f"Job {job.id} failed after {self.max_retries} retries: {error_msg}")
        await self.update_status(job, JobStatus.FAILED, error=error_msg)
        return False

    async def recover_incomplete_jobs(
        self,
        process_func: Callable[[str], Awaitable[None]],
    ) -> int:
        """
        Recover and restart incomplete jobs.

        Args:
            process_func: Function to process a job by ID

        Returns:
            Number of jobs recovered
        """
        incomplete_statuses = {
            JobStatus.PENDING,
            JobStatus.DOWNLOADING,
            JobStatus.TRANSCRIBING,
            JobStatus.DIARIZING,
            JobStatus.TRANSLATING,
            JobStatus.EXPORTING,
        }

        recovered = 0
        for job in self.jobs.values():
            if job.status in incomplete_statuses:
                logger.info(f"Recovering job {job.id} from status {job.status}")

                # Reset to pending and reprocess
                await self.update_status(job, JobStatus.PENDING, progress=0.0)
                asyncio.create_task(process_func(job.id))
                recovered += 1

        return recovered

    def get_stats(self) -> Dict:
        """Get job statistics."""
        stats = {
            "total": len(self.jobs),
            "by_status": {},
        }

        for status in JobStatus:
            count = sum(1 for j in self.jobs.values() if j.status == status)
            if count > 0:
                stats["by_status"][status.value] = count

        return stats

    # ========== v2: Additional methods ==========

    def set_item_manager(self, item_manager: "ItemManager") -> None:
        """Set the item manager for v2 pipeline status updates."""
        self.item_manager = item_manager

    def set_ws_broadcast_callback(
        self,
        callback: Callable[[str, dict], Awaitable[None]],
    ) -> None:
        """Set the WebSocket broadcast callback for real-time updates."""
        self.ws_broadcast_callback = callback

    def get_jobs_by_item(self, item_id: str) -> List[Job]:
        """Get all jobs for a specific item."""
        return [j for j in self.jobs.values() if j.item_id == item_id]

    def get_jobs_by_source(self, source_id: str) -> List[Job]:
        """Get all jobs for a specific source."""
        return [j for j in self.jobs.values() if j.source_id == source_id]

    def get_jobs_by_pipeline(self, pipeline_id: str) -> List[Job]:
        """Get all jobs for a specific pipeline configuration."""
        return [j for j in self.jobs.values() if j.pipeline_id == pipeline_id]

    def get_active_jobs_count(self) -> int:
        """Get count of jobs that are currently processing."""
        active_statuses = {
            JobStatus.DOWNLOADING,
            JobStatus.TRANSCRIBING,
            JobStatus.DIARIZING,
            JobStatus.TRANSLATING,
            JobStatus.EXPORTING,
        }
        return sum(1 for j in self.jobs.values() if j.status in active_statuses)

    def get_stats_by_source_type(self) -> Dict[str, Dict]:
        """Get job statistics grouped by source type (v2)."""
        result: Dict[str, Dict] = {}

        for source_type in SourceType:
            type_jobs = [j for j in self.jobs.values() if j.source_type == source_type]
            if not type_jobs:
                continue

            result[source_type.value] = {
                "total": len(type_jobs),
                "by_status": {},
            }

            for status in JobStatus:
                count = sum(1 for j in type_jobs if j.status == status)
                if count > 0:
                    result[source_type.value]["by_status"][status.value] = count

        return result
