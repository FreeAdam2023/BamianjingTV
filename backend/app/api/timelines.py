"""Timeline API routes for review UI - CRUD operations."""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.timeline import Timeline, TimelineSummary
from app.services.timeline_manager import TimelineManager
from app.workers.export import ExportWorker
from app.workers.youtube import YouTubeWorker
from app.workers.thumbnail import ThumbnailWorker
from app.workers.waveform import WaveformWorker

router = APIRouter(prefix="/timelines", tags=["timelines"])

# Module-level manager (set at startup)
_timeline_manager: Optional[TimelineManager] = None
_export_worker: Optional[ExportWorker] = None
_youtube_worker: Optional[YouTubeWorker] = None
_thumbnail_worker: Optional[ThumbnailWorker] = None
_waveform_worker: Optional[WaveformWorker] = None
_jobs_dir: Optional[Path] = None


def set_timeline_manager(manager: TimelineManager) -> None:
    """Set the timeline manager instance."""
    global _timeline_manager
    _timeline_manager = manager


def set_export_worker(worker: ExportWorker) -> None:
    """Set the export worker instance."""
    global _export_worker
    _export_worker = worker


def set_youtube_worker(worker: YouTubeWorker) -> None:
    """Set the YouTube worker instance."""
    global _youtube_worker
    _youtube_worker = worker


def set_jobs_dir(jobs_dir: Path) -> None:
    """Set the jobs directory."""
    global _jobs_dir
    _jobs_dir = jobs_dir


def _get_jobs_dir() -> Optional[Path]:
    """Get the jobs directory."""
    return _jobs_dir


def set_thumbnail_worker(worker: ThumbnailWorker) -> None:
    """Set the thumbnail worker instance."""
    global _thumbnail_worker
    _thumbnail_worker = worker


def set_waveform_worker(worker: WaveformWorker) -> None:
    """Set the waveform worker instance."""
    global _waveform_worker
    _waveform_worker = worker


def _get_manager() -> TimelineManager:
    """Get the timeline manager instance."""
    if _timeline_manager is None:
        raise RuntimeError("TimelineManager not initialized")
    return _timeline_manager


def _get_export_worker() -> ExportWorker:
    """Get the export worker instance."""
    if _export_worker is None:
        raise RuntimeError("ExportWorker not initialized")
    return _export_worker


def _get_youtube_worker() -> YouTubeWorker:
    """Get the YouTube worker instance."""
    if _youtube_worker is None:
        raise RuntimeError("YouTubeWorker not initialized")
    return _youtube_worker


def _get_thumbnail_worker() -> ThumbnailWorker:
    """Get the thumbnail worker instance."""
    if _thumbnail_worker is None:
        raise RuntimeError("ThumbnailWorker not initialized")
    return _thumbnail_worker


def _get_waveform_worker() -> WaveformWorker:
    """Get the waveform worker instance."""
    if _waveform_worker is None:
        raise RuntimeError("WaveformWorker not initialized")
    return _waveform_worker


# ============ Timeline CRUD Endpoints ============


@router.get("", response_model=List[TimelineSummary])
async def list_timelines(
    reviewed_only: bool = Query(default=False, description="Only reviewed timelines"),
    unreviewed_only: bool = Query(
        default=False, description="Only unreviewed timelines"
    ),
    limit: int = Query(default=100, le=500, description="Maximum results"),
):
    """List all timelines with optional filtering."""
    manager = _get_manager()
    return manager.list_timelines(
        reviewed_only=reviewed_only,
        unreviewed_only=unreviewed_only,
        limit=limit,
    )


@router.get("/stats")
async def get_timeline_stats():
    """Get timeline statistics."""
    manager = _get_manager()
    return manager.get_stats()


@router.get("/by-job/{job_id}", response_model=Timeline)
async def get_timeline_by_job(job_id: str):
    """Get timeline by job ID."""
    manager = _get_manager()
    timeline = manager.get_timeline_by_job(job_id)
    if not timeline:
        raise HTTPException(
            status_code=404, detail=f"No timeline found for job {job_id}"
        )
    return timeline


@router.get("/{timeline_id}", response_model=Timeline)
async def get_timeline(timeline_id: str):
    """Get a specific timeline with all segments."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")
    return timeline


@router.delete("/{timeline_id}")
async def delete_timeline(timeline_id: str):
    """Delete a timeline."""
    manager = _get_manager()
    if not manager.delete_timeline(timeline_id):
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {"message": f"Timeline {timeline_id} deleted"}


@router.post("/{timeline_id}/mark-reviewed")
async def mark_timeline_reviewed(timeline_id: str):
    """Mark a timeline as reviewed."""
    manager = _get_manager()
    if not manager.mark_reviewed(timeline_id):
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {"message": f"Timeline {timeline_id} marked as reviewed"}


@router.post("/{timeline_id}/subtitle-ratio")
async def set_subtitle_area_ratio(timeline_id: str, ratio: float = Query(..., ge=0.3, le=0.7)):
    """Set subtitle area ratio for WYSIWYG export layout.

    The ratio determines how much of the screen height is dedicated to subtitles.
    Valid range: 0.3 to 0.7 (30% to 70% of screen height).
    Default is 0.5 (50%).
    """
    manager = _get_manager()
    if not manager.set_subtitle_area_ratio(timeline_id, ratio):
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {
        "timeline_id": timeline_id,
        "subtitle_area_ratio": ratio,
        "message": f"Subtitle area ratio set to {ratio:.0%}",
    }
