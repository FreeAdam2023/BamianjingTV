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


from pydantic import BaseModel
from typing import List


class SegmentSplitRequest(BaseModel):
    """Request model for splitting a segment."""
    en_split_index: int  # Character index to split English text
    zh_split_index: int  # Character index to split Chinese text


class SegmentSplitResponse(BaseModel):
    """Response model for split operation."""
    original_id: int
    new_segments: List[EditableSegment]
    message: str


@router.post("/{timeline_id}/segments/{segment_id}/split", response_model=SegmentSplitResponse)
async def split_segment(
    timeline_id: str,
    segment_id: int,
    request: SegmentSplitRequest,
):
    """Split a long segment into two segments.

    The time is divided proportionally based on the English text split position.
    Both EN and ZH texts are split at the specified indices.

    Args:
        timeline_id: Timeline ID
        segment_id: ID of segment to split
        request: Split indices for EN and ZH text
    """
    manager = _get_manager()
    timeline = manager.get_timeline(timeline_id)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Find the segment
    segment_idx = None
    segment = None
    for i, seg in enumerate(timeline.segments):
        if seg.id == segment_id:
            segment_idx = i
            segment = seg
            break

    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    # Validate split indices
    en_text = segment.text or ""
    zh_text = segment.translation or ""

    if request.en_split_index <= 0 or request.en_split_index >= len(en_text):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid EN split index. Must be between 1 and {len(en_text)-1}"
        )
    if request.zh_split_index <= 0 or request.zh_split_index >= len(zh_text):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ZH split index. Must be between 1 and {len(zh_text)-1}"
        )

    # Calculate time split based on EN text proportion
    en_ratio = request.en_split_index / len(en_text)
    duration = segment.end - segment.start
    split_time = segment.start + (duration * en_ratio)

    # Split texts
    en_part1 = en_text[:request.en_split_index].strip()
    en_part2 = en_text[request.en_split_index:].strip()
    zh_part1 = zh_text[:request.zh_split_index].strip()
    zh_part2 = zh_text[request.zh_split_index:].strip()

    # Create new segment IDs
    max_id = max(seg.id for seg in timeline.segments)
    new_id_1 = max_id + 1
    new_id_2 = max_id + 2

    # Create two new segments
    new_seg_1 = EditableSegment(
        id=new_id_1,
        start=segment.start,
        end=split_time,
        text=en_part1,
        translation=zh_part1,
        speaker=segment.speaker,
        state=segment.state,
    )

    new_seg_2 = EditableSegment(
        id=new_id_2,
        start=split_time,
        end=segment.end,
        text=en_part2,
        translation=zh_part2,
        speaker=segment.speaker,
        state=segment.state,
    )

    # Replace old segment with two new ones
    timeline.segments = (
        timeline.segments[:segment_idx] +
        [new_seg_1, new_seg_2] +
        timeline.segments[segment_idx + 1:]
    )

    # Save timeline
    manager.save_timeline(timeline)

    return SegmentSplitResponse(
        original_id=segment_id,
        new_segments=[new_seg_1, new_seg_2],
        message=f"Segment {segment_id} split into {new_id_1} and {new_id_2}",
    )
