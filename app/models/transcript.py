"""Transcript data models."""

from typing import List, Optional
from pydantic import BaseModel


class Segment(BaseModel):
    """A single transcript segment."""

    start: float
    end: float
    text: str


class DiarizedSegment(Segment):
    """A transcript segment with speaker information."""

    speaker: str


class TranslatedSegment(DiarizedSegment):
    """A transcript segment with translation."""

    translation: str


class Transcript(BaseModel):
    """Full transcript data."""

    language: str
    segments: List[Segment]


class DiarizedTranscript(BaseModel):
    """Transcript with speaker diarization."""

    language: str
    num_speakers: int
    segments: List[DiarizedSegment]


class TranslatedTranscript(BaseModel):
    """Transcript with translations."""

    source_language: str
    target_language: str
    num_speakers: int
    segments: List[TranslatedSegment]
