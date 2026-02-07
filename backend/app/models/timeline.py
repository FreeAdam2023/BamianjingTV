"""Timeline data models for review UI."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


# ============ Observation Types (for WATCHING mode) ============


class ObservationType(str, Enum):
    """Type of observation/scene capture."""

    SLANG = "slang"  # Slang expressions, idioms
    PROP = "prop"  # Props, objects in scene
    CHARACTER = "character"  # Character observations
    MUSIC = "music"  # Background music, songs
    VISUAL = "visual"  # Visual gags, cinematography
    GENERAL = "general"  # General observations


class CropRegion(BaseModel):
    """Region for cropped frame capture."""

    x: int
    y: int
    width: int
    height: int


class Observation(BaseModel):
    """A single observation/capture during watching session."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    timecode: float  # Timestamp in video (seconds)
    frame_path: str  # Path to full frame capture
    crop_path: Optional[str] = None  # Path to cropped region
    crop_region: Optional[CropRegion] = None
    note: str  # User's note about the observation
    tag: ObservationType = ObservationType.GENERAL
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def timecode_str(self) -> str:
        """Get timecode as HH:MM:SS string."""
        hours = int(self.timecode // 3600)
        minutes = int((self.timecode % 3600) // 60)
        seconds = int(self.timecode % 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


class ObservationCreate(BaseModel):
    """Request model for creating an observation."""

    timecode: float
    note: str
    tag: ObservationType = ObservationType.GENERAL
    crop_region: Optional[CropRegion] = None


# ============ Segment and Timeline Types ============


class SegmentState(str, Enum):
    """Segment state for review."""

    KEEP = "keep"
    DROP = "drop"
    UNDECIDED = "undecided"


class ExportProfile(str, Enum):
    """Export profile options."""

    FULL = "full"  # Full video with all segments
    ESSENCE = "essence"  # Only keep segments
    BOTH = "both"  # Export both versions


class ExportStatus(str, Enum):
    """Export task status."""

    IDLE = "idle"  # No export running
    EXPORTING = "exporting"  # Rendering video with subtitles
    UPLOADING = "uploading"  # Uploading to YouTube
    COMPLETED = "completed"  # Export finished successfully
    FAILED = "failed"  # Export failed


class PinnedCardType(str, Enum):
    """Type of pinned card."""

    WORD = "word"
    ENTITY = "entity"
    INSIGHT = "insight"  # AI-generated insight from chat


class PinnedCard(BaseModel):
    """A card pinned to the timeline for display in exported video."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    card_type: PinnedCardType  # word or entity
    card_id: str  # word string or entity QID
    segment_id: int  # Associated segment ID
    timestamp: float  # Time when card was pinned (seconds)
    display_start: float  # When to start showing card
    display_end: float  # When to stop showing card
    card_data: Optional[dict] = None  # Cached card data for export
    created_at: datetime = Field(default_factory=datetime.now)


class PinnedCardCreate(BaseModel):
    """Request model for pinning a card."""

    card_type: PinnedCardType
    card_id: str
    segment_id: int
    timestamp: float
    card_data: Optional[dict] = None


class InsightCard(BaseModel):
    """AI-generated insight card data structure."""

    title: str  # Short title for the insight
    content: str  # Main explanation/analysis
    category: str = "general"  # general, vocabulary, expression, culture, etc.
    related_text: Optional[str] = None  # The text/line being discussed
    frame_data: Optional[str] = None  # Base64 image if screenshot was included


class SubtitleStyleMode(str, Enum):
    """Subtitle rendering style mode for export."""

    HALF_SCREEN = "half_screen"  # Learning: video on top, subtitles in bottom area
    FLOATING = "floating"  # Watching: transparent subtitles over video
    NONE = "none"  # Dubbing: no subtitles


class SubtitleLanguageMode(str, Enum):
    """Which subtitle languages to display."""

    BOTH = "both"  # Show both EN and ZH subtitles
    EN = "en"  # Show only English (original)
    ZH = "zh"  # Show only Chinese (translation)
    NONE = "none"  # No subtitles


class EditableSegment(BaseModel):
    """An editable transcript segment for review."""

    id: int
    start: float
    end: float
    en: str  # English original text
    zh: str  # Chinese translation
    speaker: Optional[str] = None
    state: SegmentState = SegmentState.UNDECIDED
    trim_start: float = 0.0  # Trim from segment start (seconds)
    trim_end: float = 0.0  # Trim from segment end (seconds)

    @property
    def effective_start(self) -> float:
        """Get effective start time after trimming."""
        return self.start + self.trim_start

    @property
    def effective_end(self) -> float:
        """Get effective end time after trimming."""
        return self.end - self.trim_end

    @property
    def effective_duration(self) -> float:
        """Get effective duration after trimming."""
        return max(0, self.effective_end - self.effective_start)


class SegmentUpdate(BaseModel):
    """Request model for updating a segment."""

    state: Optional[SegmentState] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    en: Optional[str] = None
    zh: Optional[str] = None


class SegmentBatchUpdate(BaseModel):
    """Request model for batch updating segments."""

    segment_ids: List[int]
    state: SegmentState


class Timeline(BaseModel):
    """Timeline for video segment review and editing."""

    timeline_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    job_id: str
    mode: str = "learning"  # JobMode: learning, watching, dubbing
    source_url: str
    source_title: str
    source_duration: float  # Total video duration in seconds
    segments: List[EditableSegment]
    is_reviewed: bool = False
    export_profile: ExportProfile = ExportProfile.FULL
    use_traditional_chinese: bool = True  # Traditional vs Simplified
    subtitle_area_ratio: float = 0.5  # Ratio of screen height for subtitle area (0.3-0.7)
    subtitle_style_mode: SubtitleStyleMode = SubtitleStyleMode.HALF_SCREEN  # Subtitle rendering style
    subtitle_language_mode: SubtitleLanguageMode = SubtitleLanguageMode.BOTH  # Which languages to show

    # Video-level trim (independent of subtitle segments)
    video_trim_start: float = 0.0  # Trim video from this point (seconds)
    video_trim_end: Optional[float] = None  # Trim video to this point (None = no trim)

    # Speaker names mapping (e.g., {"SPEAKER_0": "Elon Musk", "SPEAKER_1": "Interviewer"})
    speaker_names: Dict[str, str] = Field(default_factory=dict)

    # Output paths (set after export)
    output_full_path: Optional[str] = None
    output_essence_path: Optional[str] = None

    # YouTube upload results
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None

    # Export progress tracking
    export_status: ExportStatus = ExportStatus.IDLE
    export_progress: float = 0.0  # 0-100 percentage
    export_message: Optional[str] = None  # Current step description
    export_error: Optional[str] = None  # Error message if failed
    export_started_at: Optional[datetime] = None

    # Cover frame for thumbnail
    cover_frame_time: Optional[float] = None  # Timestamp of captured cover frame

    # Observations (for WATCHING mode)
    observations: List[Observation] = Field(default_factory=list)

    # AI-generated metadata drafts (saved to avoid re-generation)
    draft_youtube_title: Optional[str] = None
    draft_youtube_description: Optional[str] = None
    draft_youtube_tags: Optional[List[str]] = None
    draft_thumbnail_candidates: Optional[List[dict]] = None  # List of {main, sub, style}
    draft_instruction: Optional[str] = None  # User's AI instruction
    draft_selected_title: Optional[dict] = None  # User's selected title {index, main, sub, style}
    draft_thumbnail_url: Optional[str] = None  # Generated thumbnail URL

    # Creative mode config (Remotion config for dynamic subtitles)
    creative_config: Optional[dict] = None  # RemotionConfig as dict

    # Entity annotations cache (keyed by segment_id)
    # Format: {segment_id: {segment_id, words: [...], entities: [...]}}
    segment_annotations: Dict[int, dict] = Field(default_factory=dict)

    # Pinned cards for export
    pinned_cards: List[PinnedCard] = Field(default_factory=list)
    card_display_duration: float = 7.0  # Default display duration in seconds (5-10 range)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @property
    def total_segments(self) -> int:
        """Get total number of segments."""
        return len(self.segments)

    @property
    def keep_count(self) -> int:
        """Get number of KEEP segments."""
        return sum(1 for seg in self.segments if seg.state == SegmentState.KEEP)

    @property
    def drop_count(self) -> int:
        """Get number of DROP segments."""
        return sum(1 for seg in self.segments if seg.state == SegmentState.DROP)

    @property
    def undecided_count(self) -> int:
        """Get number of UNDECIDED segments."""
        return sum(1 for seg in self.segments if seg.state == SegmentState.UNDECIDED)

    @property
    def keep_duration(self) -> float:
        """Get total duration of KEEP segments."""
        return sum(
            seg.effective_duration
            for seg in self.segments
            if seg.state == SegmentState.KEEP
        )

    @property
    def review_progress(self) -> float:
        """Get review progress as percentage (0-100)."""
        if not self.segments:
            return 100.0
        decided = self.keep_count + self.drop_count
        return (decided / self.total_segments) * 100

    def get_segment(self, segment_id: int) -> Optional[EditableSegment]:
        """Get segment by ID."""
        for seg in self.segments:
            if seg.id == segment_id:
                return seg
        return None

    def update_segment(
        self, segment_id: int, update: SegmentUpdate
    ) -> Optional[EditableSegment]:
        """Update a segment and return the updated segment."""
        seg = self.get_segment(segment_id)
        if not seg:
            return None

        if update.state is not None:
            seg.state = update.state
        if update.trim_start is not None:
            seg.trim_start = update.trim_start
        if update.trim_end is not None:
            seg.trim_end = update.trim_end
        if update.en is not None:
            seg.en = update.en
        if update.zh is not None:
            seg.zh = update.zh

        self.updated_at = datetime.now()
        return seg

    def batch_update_segments(self, segment_ids: List[int], state: SegmentState) -> int:
        """Batch update segment states. Returns number of segments updated."""
        updated = 0
        for seg in self.segments:
            if seg.id in segment_ids:
                seg.state = state
                updated += 1
        if updated > 0:
            self.updated_at = datetime.now()
        return updated

    def mark_reviewed(self) -> None:
        """Mark timeline as reviewed."""
        self.is_reviewed = True
        self.updated_at = datetime.now()

    # ============ Observation Methods (for WATCHING mode) ============

    @property
    def observation_count(self) -> int:
        """Get number of observations."""
        return len(self.observations)

    def get_observation(self, observation_id: str) -> Optional[Observation]:
        """Get observation by ID."""
        for obs in self.observations:
            if obs.id == observation_id:
                return obs
        return None

    def add_observation(self, observation: Observation) -> Observation:
        """Add an observation to the timeline."""
        self.observations.append(observation)
        self.updated_at = datetime.now()
        return observation

    def delete_observation(self, observation_id: str) -> bool:
        """Delete an observation. Returns True if deleted."""
        for i, obs in enumerate(self.observations):
            if obs.id == observation_id:
                del self.observations[i]
                self.updated_at = datetime.now()
                return True
        return False

    # ============ Pinned Card Methods ============

    @property
    def pinned_card_count(self) -> int:
        """Get number of pinned cards."""
        return len(self.pinned_cards)

    def get_pinned_card(self, card_id: str) -> Optional[PinnedCard]:
        """Get pinned card by ID."""
        for card in self.pinned_cards:
            if card.id == card_id:
                return card
        return None

    def is_card_pinned(self, card_type: PinnedCardType, card_id: str) -> Optional[PinnedCard]:
        """Check if a card is already pinned. Returns the pinned card if found."""
        for card in self.pinned_cards:
            if card.card_type == card_type and card.card_id == card_id:
                return card
        return None

    def add_pinned_card(self, pinned_card: PinnedCard) -> PinnedCard:
        """Add a pinned card to the timeline."""
        self.pinned_cards.append(pinned_card)
        self.updated_at = datetime.now()
        return pinned_card

    def remove_pinned_card(self, card_id: str) -> bool:
        """Remove a pinned card by ID. Returns True if removed."""
        for i, card in enumerate(self.pinned_cards):
            if card.id == card_id:
                del self.pinned_cards[i]
                self.updated_at = datetime.now()
                return True
        return False

    def calculate_card_timing(self, timestamp: float) -> tuple[float, float]:
        """Calculate display start/end times for a new pinned card.

        Logic:
        - Default display duration is card_display_duration seconds
        - Start from the pinned timestamp
        - If overlapping with previous card, delay start to after previous ends
        """
        duration = self.card_display_duration
        display_start = timestamp
        display_end = timestamp + duration

        # Check for overlap with existing cards and adjust
        for existing in sorted(self.pinned_cards, key=lambda c: c.display_start):
            # If new card overlaps with existing
            if display_start < existing.display_end and display_end > existing.display_start:
                # Push new card to start after existing ends
                display_start = existing.display_end
                display_end = display_start + duration

        return display_start, display_end

    def generate_pinned_cards_description(self, include_timestamps: bool = True) -> str:
        """Generate YouTube description section with word and entity lists.

        Args:
            include_timestamps: Include video timestamps for each card

        Returns:
            Formatted description text with word list and entity list
        """
        if not self.pinned_cards:
            return ""

        def format_timestamp(seconds: float) -> str:
            """Format seconds to MM:SS or HH:MM:SS."""
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            if hours > 0:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            return f"{minutes}:{secs:02d}"

        # Separate words and entities
        words = []
        entities = []

        for card in sorted(self.pinned_cards, key=lambda c: c.timestamp):
            if card.card_type == PinnedCardType.WORD and card.card_data:
                words.append(card)
            elif card.card_type == PinnedCardType.ENTITY and card.card_data:
                entities.append(card)

        lines = []

        # Word list section
        if words:
            lines.append("📚 词汇列表 | Vocabulary")
            lines.append("-" * 30)
            for card in words:
                data = card.card_data
                word = data.get("word", "")
                # Get IPA pronunciation
                ipa = ""
                for pron in data.get("pronunciations", []):
                    if pron.get("region") == "us" or not ipa:
                        ipa = pron.get("ipa", "")

                # Get first Chinese definition
                definition_zh = ""
                for sense in data.get("senses", []):
                    if sense.get("definition_zh"):
                        definition_zh = sense["definition_zh"]
                        break

                # Format line
                timestamp_str = f"[{format_timestamp(card.timestamp)}] " if include_timestamps else ""
                if ipa and definition_zh:
                    lines.append(f"{timestamp_str}{word} {ipa} - {definition_zh}")
                elif definition_zh:
                    lines.append(f"{timestamp_str}{word} - {definition_zh}")
                else:
                    lines.append(f"{timestamp_str}{word}")

            lines.append("")

        # Entity list section
        if entities:
            lines.append("🔗 相关链接 | Related Links")
            lines.append("-" * 30)
            for card in entities:
                data = card.card_data
                name = data.get("name", "")

                # Get Chinese name
                name_zh = ""
                localizations = data.get("localizations", {})
                if "zh" in localizations:
                    name_zh = localizations["zh"].get("name", "")

                # Get Wikipedia URL
                wiki_url = data.get("wikipedia_url", "")

                # Format line
                timestamp_str = f"[{format_timestamp(card.timestamp)}] " if include_timestamps else ""
                if name_zh and name_zh != name:
                    display_name = f"{name} ({name_zh})"
                else:
                    display_name = name

                if wiki_url:
                    lines.append(f"{timestamp_str}{display_name}")
                    lines.append(f"   ↳ {wiki_url}")
                else:
                    lines.append(f"{timestamp_str}{display_name}")

            lines.append("")

        return "\n".join(lines)


class TimelineCreate(BaseModel):
    """Request model for creating a timeline (usually auto-created from job)."""

    job_id: str
    mode: str = "learning"  # JobMode: learning, watching, dubbing
    source_url: str
    source_title: str
    source_duration: float


class SubtitleStyleOptions(BaseModel):
    """Subtitle style options for export."""

    en_font_size: int = 40  # English font size in pixels
    zh_font_size: int = 40  # Chinese font size in pixels
    en_color: str = "#ffffff"  # English text color (hex)
    zh_color: str = "#facc15"  # Chinese text color (hex)
    font_weight: str = "500"  # Font weight (400, 500, 600, 700)
    background_color: str = "#1a2744"  # Background color (hex)


class TimelineExportRequest(BaseModel):
    """Request model for triggering export."""

    profile: ExportProfile = ExportProfile.FULL
    use_traditional_chinese: bool = True

    # Subtitle style mode (half_screen, floating, none)
    subtitle_style_mode: Optional[SubtitleStyleMode] = None  # None = use timeline's setting

    # Subtitle style options
    subtitle_style: Optional[SubtitleStyleOptions] = None

    # YouTube upload options
    upload_to_youtube: bool = False
    youtube_title: Optional[str] = None  # Custom title, defaults to source_title
    youtube_description: Optional[str] = None
    youtube_tags: Optional[List[str]] = None
    youtube_privacy: str = "private"  # private, unlisted, public


class TimelineSummary(BaseModel):
    """Summary of a timeline for list views."""

    timeline_id: str
    job_id: str
    mode: str = "learning"  # JobMode: learning, watching, dubbing
    source_title: str
    source_duration: float
    total_segments: int
    keep_count: int
    drop_count: int
    undecided_count: int
    review_progress: float
    is_reviewed: bool
    # Observation count (for WATCHING mode)
    observation_count: int = 0
    # Export status
    export_status: ExportStatus = ExportStatus.IDLE
    export_progress: float = 0.0
    export_message: Optional[str] = None
    # Timestamps
    created_at: datetime
    updated_at: datetime
