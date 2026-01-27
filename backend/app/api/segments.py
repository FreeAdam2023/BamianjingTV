"""Segment API endpoints for timeline review."""

from fastapi import APIRouter, HTTPException

from app.models.timeline import (
    EditableSegment,
    SegmentBatchUpdate,
    SegmentState,
    SegmentUpdate,
)
from app.api.timelines import _get_manager

router = APIRouter(prefix="/timelines", tags=["segments"])


@router.patch("/{timeline_id}/segments/{segment_id}", response_model=EditableSegment)
async def update_segment(
    timeline_id: str,
    segment_id: int,
    update: SegmentUpdate,
):
    """Update a single segment (state, trim, text)."""
    manager = _get_manager()
    segment = manager.update_segment(timeline_id, segment_id, update)
    if not segment:
        raise HTTPException(status_code=404, detail="Timeline or segment not found")
    return segment


@router.post("/{timeline_id}/segments/batch")
async def batch_update_segments(
    timeline_id: str,
    batch: SegmentBatchUpdate,
):
    """Batch update multiple segments with the same state."""
    manager = _get_manager()
    updated = manager.batch_update_segments(
        timeline_id, batch.segment_ids, batch.state
    )
    if updated == 0:
        raise HTTPException(
            status_code=404, detail="Timeline not found or no segments matched"
        )
    return {"updated": updated, "state": batch.state.value}


@router.post("/{timeline_id}/segments/keep-all")
async def keep_all_segments(timeline_id: str):
    """Mark all segments as KEEP."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    segment_ids = [seg.id for seg in timeline.segments]
    updated = manager.batch_update_segments(timeline_id, segment_ids, SegmentState.KEEP)
    return {"updated": updated, "state": "keep"}


@router.post("/{timeline_id}/segments/drop-all")
async def drop_all_segments(timeline_id: str):
    """Mark all segments as DROP."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    segment_ids = [seg.id for seg in timeline.segments]
    updated = manager.batch_update_segments(timeline_id, segment_ids, SegmentState.DROP)
    return {"updated": updated, "state": "drop"}


@router.post("/{timeline_id}/segments/reset-all")
async def reset_all_segments(timeline_id: str):
    """Reset all segments to UNDECIDED."""
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    segment_ids = [seg.id for seg in timeline.segments]
    updated = manager.batch_update_segments(
        timeline_id, segment_ids, SegmentState.UNDECIDED
    )
    return {"updated": updated, "state": "undecided"}


@router.post("/{timeline_id}/segments/drop-before")
async def drop_segments_before(timeline_id: str, time: float):
    """Drop all segments that END before the specified time.

    Use this to cut off the beginning of a video (e.g., waiting time before content starts).

    Args:
        timeline_id: Timeline ID
        time: Timestamp in seconds. Segments ending before this time will be dropped.
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Find segments that end before the specified time
    segment_ids = [seg.id for seg in timeline.segments if seg.end <= time]

    if not segment_ids:
        return {"updated": 0, "state": "drop", "message": "No segments found before this time"}

    updated = manager.batch_update_segments(timeline_id, segment_ids, SegmentState.DROP)
    return {"updated": updated, "state": "drop", "time": time}


@router.post("/{timeline_id}/segments/drop-after")
async def drop_segments_after(timeline_id: str, time: float):
    """Drop all segments that START after the specified time.

    Use this to cut off the end of a video.

    Args:
        timeline_id: Timeline ID
        time: Timestamp in seconds. Segments starting after this time will be dropped.
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Find segments that start after the specified time
    segment_ids = [seg.id for seg in timeline.segments if seg.start >= time]

    if not segment_ids:
        return {"updated": 0, "state": "drop", "message": "No segments found after this time"}

    updated = manager.batch_update_segments(timeline_id, segment_ids, SegmentState.DROP)
    return {"updated": updated, "state": "drop", "time": time}
