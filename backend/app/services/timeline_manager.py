"""Timeline manager service for review UI."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from loguru import logger

from app.config import settings
from app.models.timeline import (
    EditableSegment,
    ExportProfile,
    ExportStatus,
    Observation,
    ObservationCreate,
    PinnedCard,
    PinnedCardCreate,
    PinnedCardType,
    SegmentState,
    SegmentUpdate,
    Timeline,
    TimelineSummary,
)
from app.models.transcript import TranslatedTranscript


class TimelineManager:
    """Manager for timeline CRUD operations."""

    def __init__(self, timelines_dir: Optional[Path] = None):
        """Initialize timeline manager.

        Args:
            timelines_dir: Directory for timeline storage.
                          Defaults to data_dir/timelines.
        """
        self.timelines_dir = timelines_dir or settings.data_dir / "timelines"
        self.timelines_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Timeline] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all timelines from disk."""
        self._cache.clear()
        for file_path in self.timelines_dir.glob("*.json"):
            try:
                timeline = self._load_timeline(file_path)
                self._cache[timeline.timeline_id] = timeline
            except Exception as e:
                logger.warning(f"Failed to load timeline {file_path}: {e}")

        logger.info(f"Loaded {len(self._cache)} timelines")

    def _load_timeline(self, file_path: Path) -> Timeline:
        """Load a timeline from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Timeline.model_validate(data)

    def _save_timeline(self, timeline: Timeline) -> None:
        """Save a timeline to disk."""
        file_path = self.timelines_dir / f"{timeline.timeline_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(timeline.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

    def create_from_transcript(
        self,
        job_id: str,
        source_url: str,
        source_title: str,
        source_duration: float,
        translated_transcript: TranslatedTranscript,
        mode: str = "learning",
    ) -> Timeline:
        """Create a new timeline from a translated transcript.

        Args:
            job_id: Associated job ID
            source_url: Original video URL
            source_title: Original video title
            source_duration: Video duration in seconds
            translated_transcript: Translated transcript with segments
            mode: Job mode (learning, watching, dubbing)

        Returns:
            Created Timeline object
        """
        segments = []
        for i, seg in enumerate(translated_transcript.segments):
            segments.append(
                EditableSegment(
                    id=i,
                    start=seg.start,
                    end=seg.end,
                    en=seg.text,
                    zh=seg.translation,
                    speaker=seg.speaker if hasattr(seg, "speaker") else None,
                    state=SegmentState.UNDECIDED,
                )
            )

        timeline = Timeline(
            job_id=job_id,
            mode=mode,
            source_url=source_url,
            source_title=source_title,
            source_duration=source_duration,
            segments=segments,
        )

        self._cache[timeline.timeline_id] = timeline
        self._save_timeline(timeline)
        logger.info(
            f"Created timeline {timeline.timeline_id} for job {job_id} "
            f"with {len(segments)} segments"
        )

        return timeline

    def get_timeline(self, timeline_id: str) -> Optional[Timeline]:
        """Get a timeline by ID."""
        return self._cache.get(timeline_id)

    def get_timeline_by_job(self, job_id: str) -> Optional[Timeline]:
        """Get a timeline by job ID."""
        for timeline in self._cache.values():
            if timeline.job_id == job_id:
                return timeline
        return None

    def list_timelines(
        self,
        reviewed_only: bool = False,
        unreviewed_only: bool = False,
        limit: int = 100,
    ) -> List[TimelineSummary]:
        """List timelines with optional filtering.

        Args:
            reviewed_only: Only return reviewed timelines
            unreviewed_only: Only return unreviewed timelines
            limit: Maximum number of results

        Returns:
            List of TimelineSummary objects
        """
        result = []
        for timeline in sorted(
            self._cache.values(),
            key=lambda t: t.updated_at,
            reverse=True,
        ):
            if reviewed_only and not timeline.is_reviewed:
                continue
            if unreviewed_only and timeline.is_reviewed:
                continue

            result.append(
                TimelineSummary(
                    timeline_id=timeline.timeline_id,
                    job_id=timeline.job_id,
                    mode=timeline.mode,
                    source_title=timeline.source_title,
                    source_duration=timeline.source_duration,
                    total_segments=timeline.total_segments,
                    keep_count=timeline.keep_count,
                    drop_count=timeline.drop_count,
                    undecided_count=timeline.undecided_count,
                    review_progress=timeline.review_progress,
                    is_reviewed=timeline.is_reviewed,
                    observation_count=timeline.observation_count,
                    export_status=timeline.export_status,
                    export_progress=timeline.export_progress,
                    export_message=timeline.export_message,
                    created_at=timeline.created_at,
                    updated_at=timeline.updated_at,
                )
            )

            if len(result) >= limit:
                break

        return result

    def update_segment(
        self,
        timeline_id: str,
        segment_id: int,
        update: SegmentUpdate,
    ) -> Optional[EditableSegment]:
        """Update a single segment.

        Args:
            timeline_id: Timeline ID
            segment_id: Segment ID to update
            update: Update data

        Returns:
            Updated segment or None if not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return None

        segment = timeline.update_segment(segment_id, update)
        if segment:
            self._save_timeline(timeline)
            logger.debug(f"Updated segment {segment_id} in timeline {timeline_id}")

        return segment

    def batch_update_segments(
        self,
        timeline_id: str,
        segment_ids: List[int],
        state: SegmentState,
    ) -> int:
        """Batch update segment states.

        Args:
            timeline_id: Timeline ID
            segment_ids: List of segment IDs to update
            state: New state for all segments

        Returns:
            Number of segments updated
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return 0

        updated = timeline.batch_update_segments(segment_ids, state)
        if updated > 0:
            self._save_timeline(timeline)
            logger.info(
                f"Batch updated {updated} segments to {state.value} "
                f"in timeline {timeline_id}"
            )

        return updated

    def mark_reviewed(self, timeline_id: str) -> bool:
        """Mark a timeline as reviewed.

        Args:
            timeline_id: Timeline ID

        Returns:
            True if successful, False if timeline not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return False

        timeline.mark_reviewed()
        self._save_timeline(timeline)
        logger.info(f"Marked timeline {timeline_id} as reviewed")

        return True

    def set_export_profile(
        self,
        timeline_id: str,
        profile: ExportProfile,
        use_traditional: bool = True,
    ) -> bool:
        """Set export profile for a timeline.

        Args:
            timeline_id: Timeline ID
            profile: Export profile (full, essence, both)
            use_traditional: Use Traditional Chinese

        Returns:
            True if successful, False if timeline not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return False

        timeline.export_profile = profile
        timeline.use_traditional_chinese = use_traditional
        self._save_timeline(timeline)

        return True

    def set_speaker_names(
        self,
        timeline_id: str,
        speaker_names: dict,
    ) -> bool:
        """Set speaker display names.

        Args:
            timeline_id: Timeline ID
            speaker_names: Dict mapping speaker IDs to display names
                           e.g., {"SPEAKER_0": "Elon Musk", "SPEAKER_1": "Interviewer"}

        Returns:
            True if successful, False if timeline not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return False

        # Update speaker names (merge with existing)
        timeline.speaker_names.update(speaker_names)
        self._save_timeline(timeline)
        logger.info(f"Updated speaker names for timeline {timeline_id}: {speaker_names}")

        return True

    def set_output_paths(
        self,
        timeline_id: str,
        full_path: Optional[str] = None,
        essence_path: Optional[str] = None,
    ) -> bool:
        """Set output paths after export.

        Args:
            timeline_id: Timeline ID
            full_path: Path to full video
            essence_path: Path to essence video

        Returns:
            True if successful, False if timeline not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return False

        if full_path:
            timeline.output_full_path = full_path
        if essence_path:
            timeline.output_essence_path = essence_path
        self._save_timeline(timeline)

        return True

    def set_youtube_info(
        self,
        timeline_id: str,
        video_id: str,
        url: str,
    ) -> bool:
        """Set YouTube upload info.

        Args:
            timeline_id: Timeline ID
            video_id: YouTube video ID
            url: YouTube video URL

        Returns:
            True if successful, False if timeline not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return False

        timeline.youtube_video_id = video_id
        timeline.youtube_url = url
        self._save_timeline(timeline)
        logger.info(f"Set YouTube info for timeline {timeline_id}: {url}")

        return True

    def update_export_status(
        self,
        timeline_id: str,
        status: ExportStatus,
        progress: float = 0.0,
        message: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Update export progress for a timeline.

        Args:
            timeline_id: Timeline ID
            status: Export status (IDLE, EXPORTING, UPLOADING, COMPLETED, FAILED)
            progress: Export progress percentage (0-100)
            message: Current step description
            error: Error message if failed

        Returns:
            True if successful, False if timeline not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return False

        timeline.export_status = status
        timeline.export_progress = progress
        timeline.export_message = message
        timeline.export_error = error

        # Set start time when export begins
        if status == ExportStatus.EXPORTING and timeline.export_started_at is None:
            timeline.export_started_at = datetime.utcnow()

        # Clear start time when completed, failed, or cancelled back to idle
        if status in (ExportStatus.COMPLETED, ExportStatus.FAILED, ExportStatus.IDLE):
            timeline.export_started_at = None

        self._save_timeline(timeline)
        logger.info(
            f"Export status for timeline {timeline_id}: "
            f"{status.value} ({progress:.0f}%) - {message or 'N/A'}"
        )

        return True

    def reset_export_status(self, timeline_id: str) -> bool:
        """Reset export status to idle.

        Args:
            timeline_id: Timeline ID

        Returns:
            True if successful, False if timeline not found
        """
        return self.update_export_status(
            timeline_id,
            status=ExportStatus.IDLE,
            progress=0.0,
            message=None,
            error=None,
        )

    def save_timeline(self, timeline: Timeline) -> None:
        """Save a timeline that has been modified externally.

        Args:
            timeline: Timeline object to save

        Use this when you've modified a timeline object directly
        (e.g., converting Chinese subtitles) and need to persist changes.
        """
        timeline.updated_at = datetime.utcnow()
        self._cache[timeline.timeline_id] = timeline
        self._save_timeline(timeline)
        logger.info(f"Saved timeline {timeline.timeline_id}")

    def delete_timeline(self, timeline_id: str) -> bool:
        """Delete a timeline.

        Args:
            timeline_id: Timeline ID

        Returns:
            True if deleted, False if not found
        """
        if timeline_id not in self._cache:
            return False

        file_path = self.timelines_dir / f"{timeline_id}.json"
        if file_path.exists():
            file_path.unlink()

        del self._cache[timeline_id]
        logger.info(f"Deleted timeline {timeline_id}")

        return True

    def get_stats(self) -> dict:
        """Get timeline statistics.

        Returns:
            Statistics dict
        """
        total = len(self._cache)
        reviewed = sum(1 for t in self._cache.values() if t.is_reviewed)
        pending = total - reviewed

        return {
            "total": total,
            "reviewed": reviewed,
            "pending": pending,
        }

    # ============ Observation Methods (for WATCHING mode) ============

    def add_observation(
        self,
        timeline_id: str,
        create: ObservationCreate,
        frame_path: str,
        crop_path: Optional[str] = None,
    ) -> Optional[Observation]:
        """Add an observation to a timeline.

        Args:
            timeline_id: Timeline ID
            create: Observation creation data
            frame_path: Path to captured frame
            crop_path: Path to cropped frame (optional)

        Returns:
            Created Observation or None if timeline not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return None

        observation = Observation(
            timecode=create.timecode,
            note=create.note,
            tag=create.tag,
            frame_path=frame_path,
            crop_path=crop_path,
            crop_region=create.crop_region,
        )

        timeline.add_observation(observation)
        self._save_timeline(timeline)
        logger.info(
            f"Added observation {observation.id} to timeline {timeline_id} "
            f"at {create.timecode}s"
        )

        return observation

    def get_observations(self, timeline_id: str) -> List[Observation]:
        """Get all observations for a timeline.

        Args:
            timeline_id: Timeline ID

        Returns:
            List of observations (empty if timeline not found)
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return []
        return timeline.observations

    def get_observation(
        self,
        timeline_id: str,
        observation_id: str,
    ) -> Optional[Observation]:
        """Get a specific observation.

        Args:
            timeline_id: Timeline ID
            observation_id: Observation ID

        Returns:
            Observation or None if not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return None
        return timeline.get_observation(observation_id)

    def delete_observation(
        self,
        timeline_id: str,
        observation_id: str,
    ) -> bool:
        """Delete an observation.

        Args:
            timeline_id: Timeline ID
            observation_id: Observation ID

        Returns:
            True if deleted, False if not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return False

        if timeline.delete_observation(observation_id):
            self._save_timeline(timeline)
            logger.info(
                f"Deleted observation {observation_id} from timeline {timeline_id}"
            )
            return True

        return False

    # ============ Pinned Card Methods ============

    def get_pinned_cards(self, timeline_id: str) -> List[PinnedCard]:
        """Get all pinned cards for a timeline.

        Args:
            timeline_id: Timeline ID

        Returns:
            List of pinned cards (empty if timeline not found)
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return []
        return timeline.pinned_cards

    def add_pinned_card(
        self,
        timeline_id: str,
        create: PinnedCardCreate,
    ) -> Optional[PinnedCard]:
        """Pin a card to a timeline.

        Args:
            timeline_id: Timeline ID
            create: Pinned card creation data

        Returns:
            Created PinnedCard or None if timeline not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return None

        # Check if already pinned on the same segment
        existing = timeline.is_card_pinned(create.card_type, create.card_id, create.segment_id)
        if existing:
            logger.info(
                f"Card {create.card_type.value}:{create.card_id} already pinned "
                f"on segment {create.segment_id} in timeline {timeline_id}"
            )
            return existing

        # Enforce max 2 cards per segment
        same_seg_count = sum(1 for c in timeline.pinned_cards if c.segment_id == create.segment_id)
        if same_seg_count >= 2:
            raise ValueError(
                f"每条台词最多钉住 2 张卡片（当前台词已有 {same_seg_count} 张）"
            )

        # Calculate display timing (segment-aware to prevent spillover)
        display_start, display_end = timeline.calculate_card_timing(create.timestamp, create.segment_id)

        pinned_card = PinnedCard(
            card_type=create.card_type,
            card_id=create.card_id,
            segment_id=create.segment_id,
            timestamp=create.timestamp,
            display_start=display_start,
            display_end=display_end,
            card_data=create.card_data,
        )

        timeline.add_pinned_card(pinned_card)
        self._save_timeline(timeline)
        logger.info(
            f"Pinned {create.card_type.value} card '{create.card_id}' "
            f"to timeline {timeline_id} at {create.timestamp}s "
            f"(display: {display_start:.1f}s - {display_end:.1f}s)"
        )

        return pinned_card

    def remove_pinned_card(
        self,
        timeline_id: str,
        card_id: str,
    ) -> bool:
        """Remove a pinned card from a timeline.

        Args:
            timeline_id: Timeline ID
            card_id: Pinned card ID

        Returns:
            True if removed, False if not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return False

        if timeline.remove_pinned_card(card_id):
            self._save_timeline(timeline)
            logger.info(
                f"Removed pinned card {card_id} from timeline {timeline_id}"
            )
            return True

        return False

    def is_card_pinned(
        self,
        timeline_id: str,
        card_type: str,
        card_id: str,
        segment_id: int | None = None,
    ) -> dict:
        """Check if a card is pinned to a timeline.

        Args:
            timeline_id: Timeline ID
            card_type: Card type (word or entity)
            card_id: Card ID (word or entity QID)
            segment_id: Optional segment ID for per-segment check

        Returns:
            Dict with is_pinned and optional pin_id
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return {"is_pinned": False}

        try:
            pinned_type = PinnedCardType(card_type)
        except ValueError:
            return {"is_pinned": False}

        existing = timeline.is_card_pinned(pinned_type, card_id, segment_id)
        if existing:
            return {"is_pinned": True, "pin_id": existing.id}
        return {"is_pinned": False}

    def set_card_display_duration(
        self,
        timeline_id: str,
        duration: float,
    ) -> bool:
        """Set the default display duration for pinned cards.

        Args:
            timeline_id: Timeline ID
            duration: Duration in seconds (5-10 recommended)

        Returns:
            True if successful, False if timeline not found
        """
        timeline = self.get_timeline(timeline_id)
        if not timeline:
            return False

        # Clamp to reasonable range
        timeline.card_display_duration = max(3.0, min(15.0, duration))
        self._save_timeline(timeline)
        logger.info(
            f"Set card display duration for timeline {timeline_id}: "
            f"{timeline.card_display_duration}s"
        )

        return True
