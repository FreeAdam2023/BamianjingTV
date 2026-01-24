"""Job manager with error recovery and retry logic."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Callable, Awaitable
from loguru import logger

from app.config import settings
from app.models.job import Job, JobStatus


class JobManager:
    """Manages job lifecycle with error recovery and retry support."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        webhook_callback: Optional[Callable[[Job], Awaitable[None]]] = None,
    ):
        self.jobs: Dict[str, Job] = {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.webhook_callback = webhook_callback
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

    def create_job(self, url: str, target_language: str = "zh") -> Job:
        """Create a new job."""
        job = Job(url=url, target_language=target_language)
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
        limit: int = 100,
    ) -> list[Job]:
        """List jobs, optionally filtered by status."""
        jobs = list(self.jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

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

        # Trigger webhook callback
        if self.webhook_callback:
            try:
                await self.webhook_callback(job)
            except Exception as e:
                logger.error(f"Webhook callback failed for job {job.id}: {e}")

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
            JobStatus.SYNTHESIZING,
            JobStatus.MUXING,
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
