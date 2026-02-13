"""Tests for sentence-level re-segmentation of Whisper output."""

from dataclasses import dataclass, field
from typing import List, Optional

import pytest

from app.workers.resegment import (
    MAX_SEGMENT_DURATION,
    MIN_SEGMENT_DURATION,
    MIN_WORD_COUNT,
    _clean_text,
    _flatten_words,
    _group_into_sentences,
    _has_clause_punctuation,
    _is_sentence_boundary,
    _merge_short_segments,
    _split_long_segment,
    _Word,
    _WordGroup,
    resegment_words,
)


# ---------------------------------------------------------------------------
# Test helpers: mock Whisper Word and Segment objects
# ---------------------------------------------------------------------------

@dataclass
class MockWord:
    """Mimics faster-whisper Word object."""
    start: float
    end: float
    word: str
    probability: float = 0.9


@dataclass
class MockSegment:
    """Mimics faster-whisper Segment object."""
    start: float
    end: float
    text: str
    words: Optional[List[MockWord]] = None


def _make_words(texts: List[str], start: float = 0.0, gap: float = 0.3) -> List[MockWord]:
    """Create a list of MockWord with evenly spaced timings."""
    words = []
    t = start
    for text in texts:
        words.append(MockWord(start=t, end=t + gap, word=text))
        t += gap + 0.05  # small gap between words
    return words


def _make_segment(texts: List[str], start: float = 0.0, gap: float = 0.3) -> MockSegment:
    """Create a MockSegment with words."""
    words = _make_words(texts, start, gap)
    text = " ".join(texts)
    return MockSegment(
        start=words[0].start,
        end=words[-1].end,
        text=text,
        words=words,
    )


# ---------------------------------------------------------------------------
# Tests: _is_sentence_boundary
# ---------------------------------------------------------------------------

class TestIsSentenceBoundary:
    def test_question_mark(self):
        assert _is_sentence_boundary("hello?") is True

    def test_exclamation_mark(self):
        assert _is_sentence_boundary("wow!") is True

    def test_period_normal(self):
        assert _is_sentence_boundary("hello.") is True

    def test_no_punctuation(self):
        assert _is_sentence_boundary("hello") is False

    def test_comma_not_boundary(self):
        assert _is_sentence_boundary("hello,") is False

    def test_abbreviation_dr(self):
        assert _is_sentence_boundary("Dr.") is False

    def test_abbreviation_mr(self):
        assert _is_sentence_boundary("Mr.") is False

    def test_abbreviation_mrs(self):
        assert _is_sentence_boundary("Mrs.") is False

    def test_abbreviation_us(self):
        assert _is_sentence_boundary("U.S.") is False

    def test_abbreviation_eg(self):
        assert _is_sentence_boundary("e.g.") is False

    def test_abbreviation_ie(self):
        assert _is_sentence_boundary("i.e.") is False

    def test_abbreviation_etc(self):
        assert _is_sentence_boundary("etc.") is False

    def test_abbreviation_case_insensitive(self):
        assert _is_sentence_boundary("DR.") is False
        assert _is_sentence_boundary("dr.") is False

    def test_decimal_number(self):
        assert _is_sentence_boundary("3.14") is False

    def test_version_number(self):
        assert _is_sentence_boundary("2.0") is False

    def test_ellipsis_three_dots(self):
        assert _is_sentence_boundary("well...") is False

    def test_ellipsis_two_dots(self):
        assert _is_sentence_boundary("well..") is False

    def test_single_letter_dot(self):
        assert _is_sentence_boundary("J.") is False
        assert _is_sentence_boundary("A.") is False

    def test_empty_string(self):
        assert _is_sentence_boundary("") is False

    def test_whitespace_only(self):
        assert _is_sentence_boundary("   ") is False

    def test_abbreviation_inc(self):
        assert _is_sentence_boundary("Inc.") is False

    def test_abbreviation_prof(self):
        assert _is_sentence_boundary("Prof.") is False


# ---------------------------------------------------------------------------
# Tests: _has_clause_punctuation
# ---------------------------------------------------------------------------

class TestHasClausePunctuation:
    def test_comma(self):
        assert _has_clause_punctuation("hello,") is True

    def test_semicolon(self):
        assert _has_clause_punctuation("however;") is True

    def test_colon(self):
        assert _has_clause_punctuation("note:") is True

    def test_no_clause_punct(self):
        assert _has_clause_punctuation("hello") is False

    def test_period_not_clause(self):
        assert _has_clause_punctuation("hello.") is False


# ---------------------------------------------------------------------------
# Tests: _flatten_words
# ---------------------------------------------------------------------------

class TestFlattenWords:
    def test_normal_segments_with_words(self):
        seg = _make_segment(["Hello", "world."])
        words = _flatten_words([seg])
        assert words is not None
        assert len(words) == 2
        assert words[0].word == "Hello"
        assert words[1].word == "world."

    def test_segment_without_words_fallback(self):
        seg = MockSegment(start=0.0, end=2.0, text="Hello world.", words=None)
        words = _flatten_words([seg])
        # No word-level data → returns None (fallback)
        assert words is None

    def test_mixed_segments(self):
        seg_with = _make_segment(["Hello", "world."])
        seg_without = MockSegment(start=3.0, end=5.0, text="Goodbye.", words=None)
        words = _flatten_words([seg_with, seg_without])
        assert words is not None
        # 2 words from first segment + 1 pseudo-word from second
        assert len(words) == 3
        assert words[2].word == "Goodbye."

    def test_empty_segments(self):
        assert _flatten_words([]) is None

    def test_all_no_words(self):
        seg1 = MockSegment(start=0.0, end=1.0, text="A", words=None)
        seg2 = MockSegment(start=1.0, end=2.0, text="B", words=None)
        result = _flatten_words([seg1, seg2])
        assert result is None

    def test_empty_word_text_skipped(self):
        seg = MockSegment(
            start=0.0, end=1.0, text="Hello",
            words=[MockWord(start=0.0, end=0.3, word="Hello"),
                   MockWord(start=0.5, end=0.6, word="  ")]
        )
        words = _flatten_words([seg])
        assert words is not None
        assert len(words) == 1


# ---------------------------------------------------------------------------
# Tests: _group_into_sentences
# ---------------------------------------------------------------------------

class TestGroupIntoSentences:
    def test_single_sentence(self):
        words = [
            _Word(0.0, 0.3, "Hello"),
            _Word(0.35, 0.65, "world."),
        ]
        groups = _group_into_sentences(words)
        assert len(groups) == 1
        assert groups[0].text == "Hello world."

    def test_two_sentences(self):
        words = [
            _Word(0.0, 0.3, "Hello."),
            _Word(0.5, 0.8, "Goodbye."),
        ]
        groups = _group_into_sentences(words)
        assert len(groups) == 2
        assert groups[0].text == "Hello."
        assert groups[1].text == "Goodbye."

    def test_no_sentence_ending(self):
        words = [
            _Word(0.0, 0.3, "Hello"),
            _Word(0.35, 0.65, "world"),
        ]
        groups = _group_into_sentences(words)
        assert len(groups) == 1
        assert groups[0].text == "Hello world"

    def test_abbreviation_no_split(self):
        words = [
            _Word(0.0, 0.3, "Dr."),
            _Word(0.35, 0.65, "Smith"),
            _Word(0.7, 1.0, "said"),
            _Word(1.05, 1.35, "hello."),
        ]
        groups = _group_into_sentences(words)
        assert len(groups) == 1
        assert "Dr. Smith said hello." == groups[0].text

    def test_empty_words(self):
        assert _group_into_sentences([]) == []


# ---------------------------------------------------------------------------
# Tests: _split_long_segment
# ---------------------------------------------------------------------------

class TestSplitLongSegment:
    def test_short_segment_unchanged(self):
        group = _WordGroup(words=[
            _Word(0.0, 0.3, "Hello"),
            _Word(0.35, 0.65, "world."),
        ])
        result = _split_long_segment(group)
        assert len(result) == 1

    def test_long_segment_split_at_comma(self):
        # Create a 20s segment with a comma near the midpoint
        words = []
        for i in range(20):
            t = float(i)
            text = f"word{i},"  if i == 10 else f"word{i}"
            words.append(_Word(t, t + 0.5, text))
        group = _WordGroup(words=words)
        assert group.duration > MAX_SEGMENT_DURATION

        result = _split_long_segment(group)
        assert len(result) >= 2
        for g in result:
            assert g.duration <= MAX_SEGMENT_DURATION

    def test_long_segment_no_punctuation_splits_at_midpoint(self):
        words = []
        for i in range(20):
            t = float(i)
            words.append(_Word(t, t + 0.5, f"word{i}"))
        group = _WordGroup(words=words)

        result = _split_long_segment(group)
        assert len(result) >= 2

    def test_single_word_not_split(self):
        group = _WordGroup(words=[_Word(0.0, 20.0, "superlongword")])
        result = _split_long_segment(group)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Tests: _merge_short_segments
# ---------------------------------------------------------------------------

class TestMergeShortSegments:
    def test_short_merged_into_previous(self):
        g1 = _WordGroup(words=[_Word(0.0, 2.0, "Hello"), _Word(2.1, 3.0, "there."),
                                _Word(3.1, 4.0, "How")])
        g2 = _WordGroup(words=[_Word(4.1, 4.3, "Yeah.")])  # <1s, <3 words
        result = _merge_short_segments([g1, g2])
        assert len(result) == 1
        assert "Yeah." in result[0].text

    def test_first_short_merged_into_next(self):
        g1 = _WordGroup(words=[_Word(0.0, 0.3, "OK.")])  # <1s, <3 words
        g2 = _WordGroup(words=[_Word(0.5, 2.0, "So"), _Word(2.1, 3.0, "let"),
                                _Word(3.1, 4.0, "me"), _Word(4.1, 5.0, "explain.")])
        result = _merge_short_segments([g1, g2])
        assert len(result) == 1
        assert result[0].text.startswith("OK.")

    def test_normal_segments_unchanged(self):
        g1 = _WordGroup(words=[_Word(0.0, 2.0, "Hello"), _Word(2.1, 3.0, "there."),
                                _Word(3.1, 4.0, "How")])
        g2 = _WordGroup(words=[_Word(5.0, 7.0, "I"), _Word(7.1, 8.0, "am"),
                                _Word(8.1, 9.0, "fine.")])
        result = _merge_short_segments([g1, g2])
        assert len(result) == 2

    def test_single_segment(self):
        g = _WordGroup(words=[_Word(0.0, 0.3, "OK.")])
        result = _merge_short_segments([g])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Tests: _clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_removes_arrows(self):
        assert _clean_text(">> Hello world") == "Hello world"

    def test_removes_multiple_arrows(self):
        assert _clean_text(">> >> text >>") == "text"

    def test_collapses_spaces(self):
        assert _clean_text("Hello   world") == "Hello world"

    def test_strips(self):
        assert _clean_text("  hello  ") == "hello"


# ---------------------------------------------------------------------------
# Tests: resegment_words (integration)
# ---------------------------------------------------------------------------

class TestResegmentWords:
    def test_empty_input(self):
        assert resegment_words([]) == []

    def test_simple_two_sentences(self):
        # Each sentence needs >=3 words and >=1s to avoid merge
        words = _make_words(
            ["I", "like", "cats.", "She", "likes", "dogs."],
            start=0.0, gap=0.5,
        )
        seg = MockSegment(
            start=words[0].start,
            end=words[-1].end,
            text=" ".join(w.word for w in words),
            words=words,
        )
        result = resegment_words([seg])
        assert len(result) == 2
        assert result[0].text == "I like cats."
        assert result[1].text == "She likes dogs."

    def test_abbreviation_not_split(self):
        words = _make_words(
            ["Dr.", "Smith", "said", "hello."],
            start=0.0, gap=0.5,
        )
        seg = MockSegment(
            start=words[0].start,
            end=words[-1].end,
            text="Dr. Smith said hello.",
            words=words,
        )
        result = resegment_words([seg])
        assert len(result) == 1
        assert result[0].text == "Dr. Smith said hello."

    def test_decimal_not_split(self):
        words = _make_words(
            ["Pi", "is", "3.14", "you", "know."],
            start=0.0, gap=0.5,
        )
        seg = MockSegment(
            start=words[0].start,
            end=words[-1].end,
            text="Pi is 3.14 you know.",
            words=words,
        )
        result = resegment_words([seg])
        assert len(result) == 1
        assert "3.14" in result[0].text

    def test_ellipsis_not_split(self):
        words = _make_words(
            ["Well...", "I", "think", "so."],
            start=0.0, gap=0.5,
        )
        seg = MockSegment(
            start=words[0].start,
            end=words[-1].end,
            text="Well... I think so.",
            words=words,
        )
        result = resegment_words([seg])
        assert len(result) == 1

    def test_jk_rowling_not_split(self):
        words = _make_words(
            ["J.", "K.", "Rowling", "wrote", "this."],
            start=0.0, gap=0.5,
        )
        seg = MockSegment(
            start=words[0].start,
            end=words[-1].end,
            text="J. K. Rowling wrote this.",
            words=words,
        )
        result = resegment_words([seg])
        assert len(result) == 1

    def test_fallback_no_word_data(self):
        seg1 = MockSegment(start=0.0, end=3.0, text="Hello world.", words=None)
        seg2 = MockSegment(start=3.5, end=6.0, text="How are you?", words=None)
        result = resegment_words([seg1, seg2])
        assert len(result) == 2
        assert result[0].text == "Hello world."
        assert result[1].text == "How are you?"

    def test_arrow_cleanup(self):
        words = _make_words([">>", "Hello", "world."], start=0.0, gap=0.5)
        seg = MockSegment(
            start=words[0].start,
            end=words[-1].end,
            text=">> Hello world.",
            words=words,
        )
        result = resegment_words([seg])
        # ">>" becomes empty after cleaning, so the group text is "Hello world."
        assert len(result) >= 1
        assert ">>" not in result[0].text

    def test_timestamps_preserved(self):
        # Each sentence needs >=3 words and >=1s to avoid merge
        words = _make_words(
            ["I", "like", "cats.", "She", "likes", "dogs."],
            start=1.0, gap=0.5,
        )
        seg = MockSegment(
            start=words[0].start,
            end=words[-1].end,
            text="I like cats. She likes dogs.",
            words=words,
        )
        result = resegment_words([seg])
        assert len(result) == 2
        # First segment starts at first word
        assert result[0].start == pytest.approx(words[0].start, abs=1e-3)
        # First segment ends at "cats."
        assert result[0].end == pytest.approx(words[2].end, abs=1e-3)
        # Second segment starts at "She"
        assert result[1].start == pytest.approx(words[3].start, abs=1e-3)
        # Second segment ends at "dogs."
        assert result[1].end == pytest.approx(words[5].end, abs=1e-3)

    def test_multiple_whisper_segments_merged_then_resplit(self):
        """Two Whisper segments that break mid-sentence get properly re-aligned."""
        # Segment 1: "The quick brown fox" (mid-sentence cut)
        words1 = _make_words(["The", "quick", "brown", "fox"], start=0.0, gap=0.3)
        seg1 = MockSegment(
            start=words1[0].start, end=words1[-1].end,
            text="The quick brown fox",
            words=words1,
        )
        # Segment 2: "jumps over the fence. That was cool." (continuation + new sentence)
        words2 = _make_words(
            ["jumps", "over", "the", "fence.", "That", "was", "cool."],
            start=words1[-1].end + 0.1, gap=0.3,
        )
        seg2 = MockSegment(
            start=words2[0].start, end=words2[-1].end,
            text="jumps over the fence. That was cool.",
            words=words2,
        )

        result = resegment_words([seg1, seg2])
        # Should produce 2 sentences, not matching the original 2 segments
        assert len(result) == 2
        assert "fox jumps over the fence." in result[0].text
        assert "That was cool." in result[1].text

    def test_short_segment_gets_merged(self):
        """A very short segment (e.g. 'Yeah.') gets merged with neighbor."""
        words1 = _make_words(["That", "is", "great."], start=0.0, gap=0.5)
        words2 = _make_words(["Yeah."], start=2.0, gap=0.2)  # very short
        seg = MockSegment(
            start=words1[0].start,
            end=words2[-1].end,
            text="That is great. Yeah.",
            words=words1 + words2,
        )
        result = resegment_words([seg])
        # "Yeah." is <1s and <3 words, should be merged
        assert len(result) == 1
        assert "Yeah." in result[0].text

    def test_long_segment_with_comma_gets_split(self):
        """A segment >15s with commas gets split at the best comma."""
        words = []
        t = 0.0
        for i in range(30):
            text = f"word{i}," if i == 15 else f"word{i}"
            words.append(MockWord(start=t, end=t + 0.5, word=text))
            t += 0.55
        # Total duration: ~16.5s
        text = " ".join(w.word for w in words)
        seg = MockSegment(start=0.0, end=words[-1].end, text=text, words=words)

        result = resegment_words([seg])
        assert len(result) >= 2
        for s in result:
            assert s.end - s.start <= MAX_SEGMENT_DURATION + 1.0  # small tolerance

    def test_segment_words_empty_list(self):
        """Segment with words=[] (empty list) treated as no words."""
        seg = MockSegment(start=0.0, end=2.0, text="Hello world.", words=[])
        result = resegment_words([seg])
        # Empty words list → falsy → pseudo-word fallback. But has_any_words stays False.
        assert len(result) >= 1

    def test_mixed_question_and_statement(self):
        words = _make_words(
            ["What", "is", "that?", "It", "is", "a", "cat."],
            start=0.0, gap=0.5,
        )
        seg = MockSegment(
            start=words[0].start,
            end=words[-1].end,
            text="What is that? It is a cat.",
            words=words,
        )
        result = resegment_words([seg])
        assert len(result) == 2
        assert result[0].text == "What is that?"
        assert result[1].text == "It is a cat."

    def test_us_abbreviation_in_context(self):
        words = _make_words(
            ["The", "U.S.", "is", "large."],
            start=0.0, gap=0.5,
        )
        seg = MockSegment(
            start=words[0].start, end=words[-1].end,
            text="The U.S. is large.",
            words=words,
        )
        result = resegment_words([seg])
        assert len(result) == 1
        assert "U.S." in result[0].text
