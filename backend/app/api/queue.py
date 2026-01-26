"""Queue API endpoints.

Handles job queue management operations.
"""

from typing import List

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/queue", tags=["queue"])

# Module-level reference (set by main.py during startup)
_job_queue = None


def set_job_queue(queue):
    global _job_queue
    _job_queue = queue


class QueueStats(BaseModel):
    """Queue statistics."""
    running: bool
    max_concurrent: int
    pending: int
    active: int
    active_jobs: List[str]
    processed: int
    failed: int


@router.get("/stats", response_model=QueueStats)
async def get_queue_stats():
    """Get queue statistics."""
    return _job_queue.get_stats()


@router.post("/pause")
async def pause_queue():
    """Pause the job queue (stop accepting new jobs)."""
    await _job_queue.stop()
    return {"message": "Queue paused"}


@router.post("/resume")
async def resume_queue():
    """Resume the job queue."""
    await _job_queue.start()
    return {"message": "Queue resumed"}
