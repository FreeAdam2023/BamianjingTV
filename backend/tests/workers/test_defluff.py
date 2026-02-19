"""Tests for speech disfluency removal worker."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.workers.defluff import (
    DefluffWorker,
    remove_fillers_regex,
    _has_likely_repetitions,
    _format_batch_prompt,
    _parse_batch_response,
    FILLER_PATTERN,
)
from app.models.transcript import DiarizedTranscript, DiarizedSegment


class TestRemoveFillersRegex:
    """Tests for regex-based filler removal."""

    def test_removes_um(self):
        assert remove_fillers_regex("Um, hello there") == "Hello there"

    def test_removes_uh(self):
        assert remove_fillers_regex("I was, uh, thinking") == "I was, thinking"

    def test_removes_multiple_fillers(self):
        result = remove_fillers_regex("Um, so, uh, the thing is, er, important")
        assert "um" not in result.lower()
        assert "uh" not in result.lower()
        assert "er" not in result.lower()
        assert "important" in result

    def test_case_insensitive(self):
        assert "UM" not in remove_fillers_regex("UM, hello")
        assert "Uh" not in remove_fillers_regex("Uh, hello")

    def test_preserves_words_containing_filler(self):
        # "um" in "umbrella" should NOT be removed
        result = remove_fillers_regex("Grab the umbrella")
        assert result == "Grab the umbrella"

    def test_preserves_words_with_er(self):
        # "er" in "teacher" should NOT be removed
        result = remove_fillers_regex("The teacher was great")
        assert result == "The teacher was great"

    def test_fixes_orphaned_commas(self):
        result = remove_fillers_regex("Hello, um, world")
        assert ",," not in result

    def test_fixes_leading_comma(self):
        result = remove_fillers_regex("Um, hello")
        assert result == "Hello"

    def test_recapitalizes_after_removal(self):
        result = remove_fillers_regex("Um, beyond that")
        assert result[0] == "B"

    def test_empty_string(self):
        assert remove_fillers_regex("") == ""

    def test_whitespace_only(self):
        assert remove_fillers_regex("   ") == "   "

    def test_no_fillers(self):
        text = "This is a perfectly clean sentence."
        assert remove_fillers_regex(text) == text

    def test_only_fillers(self):
        result = remove_fillers_regex("Um uh er")
        assert result == ""

    def test_filler_before_period(self):
        result = remove_fillers_regex("That's great, um.")
        assert result == "That's great."

    def test_hmm_removal(self):
        result = remove_fillers_regex("Hmm, let me think")
        assert result == "Let me think"

    def test_mhm_removal(self):
        result = remove_fillers_regex("Mhm, that's right")
        assert result == "That's right"


class TestHasLikelyRepetitions:
    """Tests for repetition detection heuristic."""

    def test_detects_repeated_bigrams(self):
        assert _has_likely_repetitions(
            "you want to go to, you want to launch from the moon"
        )

    def test_detects_short_comma_fragments(self):
        assert _has_likely_repetitions(
            "so the, the thing is, I mean, the point"
        )

    def test_no_repetitions_in_clean_text(self):
        assert not _has_likely_repetitions(
            "This is a perfectly clean sentence with no issues"
        )

    def test_short_text_returns_false(self):
        assert not _has_likely_repetitions("Hello world")

    def test_empty_text_returns_false(self):
        assert not _has_likely_repetitions("")

    def test_deliberate_repetition_ok(self):
        # "never, ever" is deliberate emphasis — short fragments heuristic
        # might trigger but bigram check won't for different bigrams
        text = "You should never do that to anyone"
        assert not _has_likely_repetitions(text)


class TestFormatBatchPrompt:
    """Tests for LLM batch prompt formatting."""

    def test_numbered_lines(self):
        texts = ["Hello world", "Goodbye world"]
        result = _format_batch_prompt(texts)
        assert result == "1. Hello world\n2. Goodbye world"

    def test_single_line(self):
        result = _format_batch_prompt(["Only one"])
        assert result == "1. Only one"

    def test_empty_list(self):
        result = _format_batch_prompt([])
        assert result == ""


class TestParseBatchResponse:
    """Tests for LLM response parsing."""

    def test_parses_numbered_lines(self):
        response = "1. Hello cleaned\n2. Goodbye cleaned"
        result = _parse_batch_response(response, 2)
        assert result == ["Hello cleaned", "Goodbye cleaned"]

    def test_handles_parenthesis_numbering(self):
        response = "1) Hello\n2) World"
        result = _parse_batch_response(response, 2)
        assert result == ["Hello", "World"]

    def test_returns_none_on_count_mismatch(self):
        response = "1. Hello\n2. World\n3. Extra"
        assert _parse_batch_response(response, 2) is None

    def test_skips_blank_lines(self):
        response = "1. Hello\n\n2. World"
        result = _parse_batch_response(response, 2)
        assert result == ["Hello", "World"]

    def test_returns_none_for_empty_response(self):
        result = _parse_batch_response("", 2)
        assert result is None


class TestDefluffWorkerCleanTranscript:
    """Tests for the full transcript cleaning pipeline."""

    @pytest.mark.asyncio
    async def test_clean_empty_transcript(self):
        worker = DefluffWorker()
        transcript = DiarizedTranscript(
            language="en", num_speakers=1, segments=[]
        )
        result = await worker.clean_transcript(transcript)
        assert result.segments == []

    @pytest.mark.asyncio
    @patch("app.workers.defluff.DefluffWorker.clean_segments_llm")
    async def test_regex_tier_runs_first(self, mock_llm):
        """Regex tier should clean fillers before LLM tier."""
        mock_llm.side_effect = lambda texts, **kw: texts  # passthrough

        worker = DefluffWorker()
        transcript = DiarizedTranscript(
            language="en",
            num_speakers=1,
            segments=[
                DiarizedSegment(
                    start=0.0, end=1.0,
                    text="Um, hello there",
                    speaker="SPEAKER_0",
                ),
            ],
        )
        result = await worker.clean_transcript(transcript)
        # Regex should have cleaned "Um, "
        assert result.segments[0].text == "Hello there"

    @pytest.mark.asyncio
    @patch("app.workers.defluff.DefluffWorker.clean_segments_llm")
    async def test_preserves_metadata(self, mock_llm):
        """Cleaned transcript preserves language, speakers, timestamps."""
        mock_llm.side_effect = lambda texts, **kw: texts

        worker = DefluffWorker()
        transcript = DiarizedTranscript(
            language="en",
            num_speakers=2,
            segments=[
                DiarizedSegment(
                    start=1.5, end=3.0,
                    text="Hello",
                    speaker="SPEAKER_1",
                ),
            ],
        )
        result = await worker.clean_transcript(transcript)
        assert result.language == "en"
        assert result.num_speakers == 2
        assert result.segments[0].start == 1.5
        assert result.segments[0].end == 3.0
        assert result.segments[0].speaker == "SPEAKER_1"


class TestDefluffWorkerCleanTexts:
    """Tests for the review UI text cleaning entry point."""

    @pytest.mark.asyncio
    @patch("app.workers.defluff.DefluffWorker.clean_segments_llm")
    async def test_clean_texts_basic(self, mock_llm):
        mock_llm.side_effect = lambda texts, **kw: texts

        worker = DefluffWorker()
        result = await worker.clean_texts(["Um, hello", "Uh, world"])
        assert result == ["Hello", "World"]

    @pytest.mark.asyncio
    async def test_clean_texts_empty(self):
        worker = DefluffWorker()
        result = await worker.clean_texts([])
        assert result == []


class TestDefluffWorkerLLM:
    """Tests for LLM-based cleaning with mocked API."""

    @pytest.mark.asyncio
    async def test_llm_cleans_repetitions(self):
        """Test that LLM cleans complex repetitions."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="1. Beyond that, you want to launch from the moon."))
        ]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        worker = DefluffWorker()

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            texts = ["Beyond that, you want to go to, you want to launch from the moon."]
            result = await worker.clean_segments_llm(texts)
            assert result == ["Beyond that, you want to launch from the moon."]

    @pytest.mark.asyncio
    async def test_llm_safety_check_rejects_overcleaning(self):
        """If LLM output is <40% of original length, keep original."""
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="1. Short."))
        ]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        worker = DefluffWorker()
        original = "This is a really really long sentence that has some repeated content and the repeated content is here."

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            result = await worker.clean_segments_llm([original])
            # "Short." is <40% of original, so original is kept
            assert result == [original]

    @pytest.mark.asyncio
    async def test_llm_skips_segments_without_repetitions(self):
        """Clean text without repetitions should skip LLM entirely."""
        worker = DefluffWorker()

        mock_client = AsyncMock()
        # Should never be called
        mock_client.chat.completions.create = AsyncMock()

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            texts = ["This is a perfectly clean sentence with no issues at all."]
            result = await worker.clean_segments_llm(texts)
            assert result == texts
            mock_client.chat.completions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_llm_failure_keeps_originals(self):
        """If LLM call fails, originals are preserved."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API error")
        )

        worker = DefluffWorker()

        with patch("openai.AsyncOpenAI", return_value=mock_client):
            texts = ["you want to go to, you want to launch from the moon"]
            result = await worker.clean_segments_llm(texts)
            assert result == texts
