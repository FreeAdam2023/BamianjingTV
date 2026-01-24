"""Job queue for batch processing with concurrency control."""

import asyncio
from typing import Callable, Awaitable, Optional, List
from dataclasses import dataclass
from datetime import datetime
from loguru import logger


@dataclass
class QueueItem:
    """Item in the job queue."""
    job_id: str
    priority: int = 0  # Higher = more priority
    added_at: datetime = None

    def __post_init__(self):
        if self.added_at is None:
            self.added_at = datetime.now()


class JobQueue:
    """
    Async job queue with concurrency control.

    Manages batch processing with configurable concurrent workers.
    """

    def __init__(
        self,
        max_concurrent: int = 2,
        process_func: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.max_concurrent = max_concurrent
        self.process_func = process_func
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._active_jobs: set[str] = set()
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._processed_count = 0
        self._failed_count = 0

    async def start(self) -> None:
        """Start queue workers."""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting job queue with {self.max_concurrent} workers")

        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

    async def stop(self) -> None:
        """Stop queue workers gracefully."""
        self._running = False

        # Cancel all workers
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        logger.info("Job queue stopped")

    async def add(
        self,
        job_id: str,
        priority: int = 0,
    ) -> None:
        """Add a job to the queue."""
        if job_id in self._active_jobs:
            logger.warning(f"Job {job_id} is already being processed")
            return

        item = QueueItem(job_id=job_id, priority=priority)
        # Use negative priority for max-heap behavior (higher priority first)
        await self._queue.put((-priority, item.added_at, item))
        logger.info(f"Added job {job_id} to queue (priority={priority})")

    async def add_batch(
        self,
        job_ids: List[str],
        priority: int = 0,
    ) -> int:
        """Add multiple jobs to the queue."""
        added = 0
        for job_id in job_ids:
            if job_id not in self._active_jobs:
                await self.add(job_id, priority)
                added += 1
        return added

    async def _worker(self, worker_id: int) -> None:
        """Queue worker that processes jobs."""
        logger.debug(f"Worker {worker_id} started")

        while self._running:
            try:
                # Wait for a job with timeout
                try:
                    _, _, item = await asyncio.wait_for(
                        self._queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                job_id = item.job_id
                self._active_jobs.add(job_id)

                logger.info(f"Worker {worker_id} processing job {job_id}")

                try:
                    if self.process_func:
                        await self.process_func(job_id)
                    self._processed_count += 1
                except Exception as e:
                    logger.error(f"Worker {worker_id} failed on job {job_id}: {e}")
                    self._failed_count += 1
                finally:
                    self._active_jobs.discard(job_id)
                    self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Worker {worker_id} error: {e}")

        logger.debug(f"Worker {worker_id} stopped")

    @property
    def pending_count(self) -> int:
        """Number of jobs waiting in queue."""
        return self._queue.qsize()

    @property
    def active_count(self) -> int:
        """Number of jobs currently being processed."""
        return len(self._active_jobs)

    @property
    def is_busy(self) -> bool:
        """Whether queue has pending or active jobs."""
        return self.pending_count > 0 or self.active_count > 0

    def get_stats(self) -> dict:
        """Get queue statistics."""
        return {
            "running": self._running,
            "max_concurrent": self.max_concurrent,
            "pending": self.pending_count,
            "active": self.active_count,
            "active_jobs": list(self._active_jobs),
            "processed": self._processed_count,
            "failed": self._failed_count,
        }


class BatchProcessor:
    """Helper for processing batches of URLs."""

    def __init__(
        self,
        job_manager,
        queue: JobQueue,
    ):
        self.job_manager = job_manager
        self.queue = queue

    async def process_urls(
        self,
        urls: List[str],
        target_language: str = "zh",
        priority: int = 0,
    ) -> List[str]:
        """
        Create jobs for multiple URLs and add to queue.

        Returns:
            List of created job IDs
        """
        job_ids = []

        for url in urls:
            job = self.job_manager.create_job(
                url=url,
                target_language=target_language,
            )
            job_ids.append(job.id)

        # Add all to queue
        await self.queue.add_batch(job_ids, priority=priority)

        logger.info(f"Created batch of {len(job_ids)} jobs")
        return job_ids
