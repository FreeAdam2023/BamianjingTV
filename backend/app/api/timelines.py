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


from pydantic import BaseModel
from typing import Dict


class SpeakerNamesUpdate(BaseModel):
    """Request model for updating speaker names."""
    speaker_names: Dict[str, str]


@router.get("/{timeline_id}/speakers")
async def get_speakers(timeline_id: str):
    """Get unique speakers and their display names for a timeline."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Get unique speakers from segments
    unique_speakers = set()
    for seg in timeline.segments:
        if seg.speaker:
            unique_speakers.add(seg.speaker)

    # Build response with current names
    speakers = []
    for speaker_id in sorted(unique_speakers):
        speakers.append({
            "speaker_id": speaker_id,
            "display_name": timeline.speaker_names.get(speaker_id, speaker_id),
            "segment_count": sum(1 for seg in timeline.segments if seg.speaker == speaker_id),
        })

    return {
        "timeline_id": timeline_id,
        "speakers": speakers,
        "speaker_names": timeline.speaker_names,
    }


@router.post("/{timeline_id}/speakers")
async def update_speaker_names(timeline_id: str, update: SpeakerNamesUpdate):
    """Update speaker display names.

    Example: {"speaker_names": {"SPEAKER_0": "Elon Musk", "SPEAKER_1": "Interviewer"}}
    """
    manager = _get_manager()
    if not manager.set_speaker_names(timeline_id, update.speaker_names):
        raise HTTPException(status_code=404, detail="Timeline not found")
    return {
        "timeline_id": timeline_id,
        "speaker_names": update.speaker_names,
        "message": f"Updated {len(update.speaker_names)} speaker name(s)",
    }


class VideoTrimUpdate(BaseModel):
    """Request model for video-level trimming."""
    trim_start: Optional[float] = None  # Set video start time (seconds)
    trim_end: Optional[float] = None  # Set video end time (seconds), None to clear


@router.get("/{timeline_id}/trim")
async def get_video_trim(timeline_id: str):
    """Get current video trim settings."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    return {
        "timeline_id": timeline_id,
        "trim_start": timeline.video_trim_start,
        "trim_end": timeline.video_trim_end,
        "source_duration": timeline.source_duration,
        "effective_duration": (timeline.video_trim_end or timeline.source_duration) - timeline.video_trim_start,
    }


@router.post("/{timeline_id}/trim")
async def set_video_trim(timeline_id: str, update: VideoTrimUpdate):
    """Set video-level trim (cut beginning/end of video).

    This is independent of subtitle segments - it trims the actual video.
    Use trim_start to cut off waiting time at the beginning.
    Use trim_end to cut off unwanted content at the end.

    Example: {"trim_start": 453.5} to start video at 7:33.5
    Example: {"trim_start": 0, "trim_end": null} to reset trim
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Validate trim values
    if update.trim_start is not None:
        if update.trim_start < 0:
            raise HTTPException(status_code=400, detail="trim_start cannot be negative")
        if update.trim_start >= timeline.source_duration:
            raise HTTPException(status_code=400, detail="trim_start cannot exceed video duration")
        timeline.video_trim_start = update.trim_start

    if update.trim_end is not None:
        if update.trim_end <= timeline.video_trim_start:
            raise HTTPException(status_code=400, detail="trim_end must be greater than trim_start")
        if update.trim_end > timeline.source_duration:
            raise HTTPException(status_code=400, detail="trim_end cannot exceed video duration")
        timeline.video_trim_end = update.trim_end
    elif "trim_end" in (update.model_dump(exclude_unset=False) or {}):
        # Explicitly set to None to clear
        timeline.video_trim_end = None

    manager.save_timeline(timeline)

    effective_duration = (timeline.video_trim_end or timeline.source_duration) - timeline.video_trim_start

    return {
        "timeline_id": timeline_id,
        "trim_start": timeline.video_trim_start,
        "trim_end": timeline.video_trim_end,
        "source_duration": timeline.source_duration,
        "effective_duration": effective_duration,
        "message": f"Video trimmed: {timeline.video_trim_start:.1f}s - {timeline.video_trim_end or timeline.source_duration:.1f}s ({effective_duration:.1f}s)",
    }


@router.delete("/{timeline_id}/trim")
async def reset_video_trim(timeline_id: str):
    """Reset video trim to show full video."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    timeline.video_trim_start = 0.0
    timeline.video_trim_end = None
    manager.save_timeline(timeline)

    return {
        "timeline_id": timeline_id,
        "trim_start": 0.0,
        "trim_end": None,
        "source_duration": timeline.source_duration,
        "message": "Video trim reset to full duration",
    }
