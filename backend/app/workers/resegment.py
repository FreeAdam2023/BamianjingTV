"""Sentence-level re-segmentation of Whisper output.

Whisper segments often break mid-sentence due to:
1. 30-second window hard cuts
2. VAD splitting at pauses regardless of sentence boundaries

This module uses word-level timestamps (already produced by faster-whisper)
to re-segment at sentence boundaries, producing cleaner segments for
downstream translation.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

from app.models.transcript import Segment

# Maximum segment duration before forced splitting (seconds)
MAX_SEGMENT_DURATION = 15.0

# Minimum segment duration — shorter segments get merged (seconds)
MIN_SEGMENT_DURATION = 1.0

# Minimum word count — segments with fewer words get merged
MIN_WORD_COUNT = 3

# Sub-clause punctuation for splitting long segments
_CLAUSE_PUNCTUATION = {",", ";", ":"}

# Abbreviations that end with '.' but are NOT sentence boundaries.
# All stored lowercase for case-insensitive matching.
_ABBREVIATIONS = frozenset({
    # Titles
    "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "st.",
    "gen.", "gov.", "sgt.", "cpl.", "pvt.", "capt.", "maj.", "col.", "lt.",
    "rev.", "hon.",
    # Academic / professional
    "ph.d.", "m.d.", "b.a.", "m.a.", "b.s.", "m.s.", "d.d.s.", "r.n.",
    # Common abbreviations
    "vs.", "etc.", "approx.", "dept.", "est.", "vol.", "no.",
    "jan.", "feb.", "mar.", "apr.", "jun.", "jul.", "aug.",
    "sep.", "sept.", "oct.", "nov.", "dec.",
    "inc.", "ltd.", "corp.", "co.",
    "ave.", "blvd.", "rd.",
    # Latin
    "e.g.", "i.e.", "al.", "et.",
    # Countries / organizations
    "u.s.", "u.k.", "u.n.", "u.s.a.",
})

# Pattern: single letter followed by dot (e.g. "J." in "J.K. Rowling")
_SINGLE_LETTER_DOT = re.compile(r"^[A-Za-z]\.$")

# Pattern: number-dot-number (decimals, version numbers like 3.14, v2.0)
_DECIMAL_PATTERN = re.compile(r"\d+\.\d*$")

# Pattern: ellipsis (two or more dots)
_ELLIPSIS_PATTERN = re.compile(r"\.{2,}$")


@dataclass
class _Word:
    """Internal word representation with timing."""
    start: float
    end: float
    word: str


@dataclass
class _WordGroup:
    """A group of words forming a sentence or fragment."""
    words: List[_Word] = field(default_factory=list)

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def text(self) -> str:
        return " ".join(w.word for w in self.words)


def _is_sentence_boundary(word_text: str) -> bool:
    """Determine if a word ends at a sentence boundary.

    Rules:
    - '?' and '!' always indicate sentence boundaries
    - '.' indicates a boundary UNLESS it's part of:
      - A known abbreviation (Dr., Mr., U.S., etc.)
      - A decimal/version number (3.14, v2.0)
      - An ellipsis (...)
      - A single-letter abbreviation (J., A.)
    """
    stripped = word_text.strip()
    if not stripped:
        return False

    last_char = stripped[-1]

    # '?' and '!' are always boundaries
    if last_char in ("?", "!"):
        return True

    # Not ending with '.' → not a boundary
    if last_char != ".":
        return False

    # It ends with '.', check exceptions
    lower = stripped.lower()

    # Known abbreviation
    if lower in _ABBREVIATIONS:
        return False

    # Ellipsis (.. or ...)
    if _ELLIPSIS_PATTERN.search(stripped):
        return False

    # Decimal / version number (3.14, 2.0)
    if _DECIMAL_PATTERN.search(stripped):
        return False

    # Single-letter dot (J. K. etc.)
    if _SINGLE_LETTER_DOT.match(stripped):
        return False

    # Otherwise, '.' is a sentence boundary
    return True


def _has_clause_punctuation(word_text: str) -> bool:
    """Check if a word ends with sub-clause punctuation (, ; :)."""
    stripped = word_text.strip()
    return bool(stripped) and stripped[-1] in _CLAUSE_PUNCTUATION


def _flatten_words(segments_list) -> Optional[List[_Word]]:
    """Step 1: Extract all words from Whisper segments into a flat list.

    If a segment has no .words, uses the segment itself as a pseudo-word.
    Returns None if no word data is available at all.
    """
    words: List[_Word] = []
    has_any_words = False

    for seg in segments_list:
        seg_words = getattr(seg, "words", None)
        if seg_words:
            has_any_words = True
            for w in seg_words:
                text = w.word.strip() if hasattr(w, "word") else str(w.word).strip()
                if text:
                    words.append(_Word(
                        start=w.start,
                        end=w.end,
                        word=text,
                    ))
        else:
            # Fallback: use entire segment as a pseudo-word
            text = seg.text.strip() if hasattr(seg, "text") else ""
            if text:
                words.append(_Word(
                    start=seg.start,
                    end=seg.end,
                    word=text,
                ))

    if not has_any_words:
        return None

    return words if words else None


def _group_into_sentences(words: List[_Word]) -> List[_WordGroup]:
    """Steps 2-3: Group words into sentences based on boundary detection."""
    if not words:
        return []

    groups: List[_WordGroup] = []
    current = _WordGroup()

    for word in words:
        current.words.append(word)
        if _is_sentence_boundary(word.word):
            groups.append(current)
            current = _WordGroup()

    # Don't forget trailing words that didn't end with sentence punctuation
    if current.words:
        groups.append(current)

    return groups


def _split_long_segment(group: _WordGroup) -> List[_WordGroup]:
    """Step 4: Split a segment that exceeds MAX_SEGMENT_DURATION.

    Strategy:
    1. Find sub-clause punctuation (, ; :) closest to the midpoint
    2. If none found, split at the word-count midpoint
    3. Recurse until all pieces are ≤ MAX_SEGMENT_DURATION
    """
    if group.duration <= MAX_SEGMENT_DURATION or len(group.words) <= 1:
        return [group]

    mid_time = group.start + group.duration / 2

    # Try to find clause punctuation closest to midpoint
    best_idx = None
    best_dist = float("inf")
    for i, w in enumerate(group.words[:-1]):  # exclude last word
        if _has_clause_punctuation(w.word):
            dist = abs(w.end - mid_time)
            if dist < best_dist:
                best_dist = dist
                best_idx = i

    # If no clause punctuation, split at word-count midpoint
    if best_idx is None:
        best_idx = len(group.words) // 2 - 1
        if best_idx < 0:
            best_idx = 0

    left = _WordGroup(words=group.words[: best_idx + 1])
    right = _WordGroup(words=group.words[best_idx + 1 :])

    # Recurse on both halves
    result: List[_WordGroup] = []
    if left.words:
        result.extend(_split_long_segment(left))
    if right.words:
        result.extend(_split_long_segment(right))

    return result


def _merge_short_segments(groups: List[_WordGroup]) -> List[_WordGroup]:
    """Step 5: Merge segments that are too short (<1s or <3 words).

    Short segments are merged into the previous segment.
    If the first segment is short, it's merged into the next one.
    """
    if len(groups) <= 1:
        return groups

    def _is_short(g: _WordGroup) -> bool:
        return g.duration < MIN_SEGMENT_DURATION or len(g.words) < MIN_WORD_COUNT

    merged: List[_WordGroup] = []

    for group in groups:
        if not merged:
            merged.append(group)
            continue

        if _is_short(group):
            # Merge into previous
            merged[-1].words.extend(group.words)
        else:
            merged.append(group)

    # Handle case where the first segment is short: merge into next
    if len(merged) > 1 and _is_short(merged[0]):
        merged[1].words = merged[0].words + merged[1].words
        merged.pop(0)

    return merged


def _clean_text(text: str) -> str:
    """Clean segment text: remove >> artifacts and normalize whitespace."""
    text = text.replace(">>", "").strip()
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text


def _groups_to_segments(groups: List[_WordGroup]) -> List[Segment]:
    """Convert word groups to Segment model instances."""
    segments: List[Segment] = []
    for group in groups:
        text = _clean_text(group.text)
        if text:
            segments.append(Segment(
                start=round(group.start, 3),
                end=round(group.end, 3),
                text=text,
            ))
    return segments


def _fallback_segments(segments_list) -> List[Segment]:
    """Fallback: convert raw Whisper segments directly (original behavior)."""
    segments: List[Segment] = []
    for seg in segments_list:
        text = _clean_text(seg.text.strip() if hasattr(seg, "text") else "")
        if text:
            segments.append(Segment(
                start=seg.start,
                end=seg.end,
                text=text,
            ))
    return segments


def resegment_words(segments_list) -> List[Segment]:
    """Re-segment Whisper output at sentence boundaries using word timestamps.

    Args:
        segments_list: List of faster-whisper segment objects, each with
            .start, .end, .text, and optionally .words (list of Word objects
            with .start, .end, .word, .probability).

    Returns:
        List of Segment instances with sentence-aligned boundaries.
    """
    if not segments_list:
        return []

    # Step 1: Flatten words
    words = _flatten_words(segments_list)
    if words is None:
        # No word-level data available — fall back to original segments
        return _fallback_segments(segments_list)

    # Steps 2-3: Group into sentences
    groups = _group_into_sentences(words)

    # Step 4: Split long segments
    split_groups: List[_WordGroup] = []
    for group in groups:
        split_groups.extend(_split_long_segment(group))

    # Step 5: Merge short segments
    final_groups = _merge_short_segments(split_groups)

    # Convert to Segment models
    return _groups_to_segments(final_groups)
