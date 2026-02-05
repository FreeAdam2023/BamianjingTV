"""Async worker for Remotion creative mode exports."""

import asyncio
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from loguru import logger

from app.workers.remotion_renderer import (
    RemotionRenderer,
    RenderOptions,
    RenderProgress,
    RenderResult,
    remotion_renderer,
)


class CreativeExportStatus(str, Enum):
    """Status of a creative export job."""
    IDLE = "idle"
    QUEUED = "queued"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CreativeExportJob:
    """A creative mode export job."""
    timeline_id: str
    job_id: str
    segments: List[Dict[str, Any]]
    config: Dict[str, Any]
    source_video_path: Path
    output_dir: Path
    fps: int = 30
    status: CreativeExportStatus = CreativeExportStatus.QUEUED
    progress: int = 0
    error: Optional[str] = None
    output_path: Optional[str] = None


class CreativeExportWorker:
    """
    Worker that processes creative mode export jobs.

    This worker maintains a queue of export jobs and processes them
    one at a time to avoid overwhelming system resources.
    """

    def __init__(self, renderer: Optional[RemotionRenderer] = None):
        self.renderer = renderer or remotion_renderer
        self._jobs: Dict[str, CreativeExportJob] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing_task: Optional[asyncio.Task] = None
        self._status_callbacks: Dict[str, List[Callable[[CreativeExportJob], None]]] = {}

    async def start(self):
        """Start the export worker processing loop."""
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_loop())
            logger.info("Creative export worker started")

    async def stop(self):
        """Stop the export worker."""
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None
            logger.info("Creative export worker stopped")

    async def submit_job(
        self,
        timeline_id: str,
        job_id: str,
        segments: List[Dict[str, Any]],
        config: Dict[str, Any],
        source_video_path: Path,
        output_dir: Path,
        fps: int = 30,
    ) -> CreativeExportJob:
        """
        Submit a new export job to the queue.

        Args:
            timeline_id: Timeline ID
            job_id: Job ID (for locating video files)
            segments: Timeline segments (will be converted to Remotion format)
            config: RemotionConfig dictionary
            source_video_path: Path to source video
            output_dir: Directory for output files
            fps: Frames per second

        Returns:
            The created export job
        """
        # Convert segments to Remotion format
        remotion_segments = self.renderer.convert_timeline_to_remotion_segments(
            segments, fps
        )

        job = CreativeExportJob(
            timeline_id=timeline_id,
            job_id=job_id,
            segments=remotion_segments,
            config=config,
            source_video_path=source_video_path,
            output_dir=output_dir,
            fps=fps,
        )

        self._jobs[timeline_id] = job
        await self._queue.put(timeline_id)

        logger.info(f"Creative export job queued for timeline {timeline_id}")

        # Ensure worker is running
        await self.start()

        return job

    def get_job(self, timeline_id: str) -> Optional[CreativeExportJob]:
        """Get the status of an export job."""
        return self._jobs.get(timeline_id)

    def get_job_status(self, timeline_id: str) -> Dict[str, Any]:
        """Get the status of an export job as a dictionary."""
        job = self._jobs.get(timeline_id)
        if not job:
            return {
                "status": CreativeExportStatus.IDLE.value,
                "progress": 0,
            }

        return {
            "status": job.status.value,
            "progress": job.progress,
            "error": job.error,
            "output_path": job.output_path,
        }

    def add_status_callback(
        self,
        timeline_id: str,
        callback: Callable[[CreativeExportJob], None],
    ):
        """Add a callback to be called on status updates for a job."""
        if timeline_id not in self._status_callbacks:
            self._status_callbacks[timeline_id] = []
        self._status_callbacks[timeline_id].append(callback)

    def remove_status_callback(
        self,
        timeline_id: str,
        callback: Callable[[CreativeExportJob], None],
    ):
        """Remove a status callback."""
        if timeline_id in self._status_callbacks:
            try:
                self._status_callbacks[timeline_id].remove(callback)
            except ValueError:
                pass

    def _notify_status(self, job: CreativeExportJob):
        """Notify all registered callbacks of a status update."""
        callbacks = self._status_callbacks.get(job.timeline_id, [])
        for callback in callbacks:
            try:
                callback(job)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

    async def _process_loop(self):
        """Main processing loop for export jobs."""
        logger.info("Creative export worker processing loop started")

        while True:
            try:
                # Wait for a job
                timeline_id = await self._queue.get()

                job = self._jobs.get(timeline_id)
                if not job:
                    logger.warning(f"Job not found for timeline {timeline_id}")
                    continue

                # Process the job
                await self._process_job(job)

            except asyncio.CancelledError:
                logger.info("Creative export worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in creative export loop: {e}")
                await asyncio.sleep(1)  # Brief pause before continuing

    async def _process_job(self, job: CreativeExportJob):
        """Process a single export job."""
        logger.info(f"Processing creative export for timeline {job.timeline_id}")

        job.status = CreativeExportStatus.RENDERING
        job.progress = 0
        self._notify_status(job)

        def on_progress(progress: RenderProgress):
            job.progress = progress.progress
            if progress.status == "error":
                job.error = progress.error
            self._notify_status(job)

        try:
            result = await self.renderer.render_creative_export(
                timeline_id=job.timeline_id,
                job_id=job.job_id,
                segments=job.segments,
                config=job.config,
                source_video_path=job.source_video_path,
                output_dir=job.output_dir,
                fps=job.fps,
                progress_callback=on_progress,
            )

            if result.success:
                job.status = CreativeExportStatus.COMPLETED
                job.progress = 100
                job.output_path = result.output_path
                logger.info(f"Creative export completed for timeline {job.timeline_id}")
            else:
                job.status = CreativeExportStatus.FAILED
                job.error = result.error or "Unknown error"
                logger.error(f"Creative export failed for timeline {job.timeline_id}: {job.error}")

        except Exception as e:
            job.status = CreativeExportStatus.FAILED
            job.error = str(e)
            logger.error(f"Creative export exception for timeline {job.timeline_id}: {e}")

        self._notify_status(job)


# Singleton instance
creative_export_worker = CreativeExportWorker()
