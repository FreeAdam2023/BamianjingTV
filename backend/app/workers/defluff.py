"""Speech disfluency removal worker.

Cleans filler words (um, uh), false starts, self-corrections, and
unnecessary repetitions from Whisper transcripts. Uses a two-tier
approach: fast regex for simple fillers, then LLM for complex
repetitions that require semantic understanding.
"""

import re
from typing import List, Optional

from loguru import logger

from app.config import settings
from app.models.transcript import DiarizedTranscript, DiarizedSegment


# Filler words to remove via regex (case-insensitive, word-boundary)
FILLER_PATTERN = re.compile(
    r"\b(um|uh|uhh|umm|hmm|hm|er|ah|erm|mhm|uh-huh)\b",
    re.IGNORECASE,
)

# Clean up orphaned punctuation after filler removal
ORPHAN_COMMA = re.compile(r",\s*,")          # ",  ,"  → ","
LEADING_COMMA = re.compile(r"^\s*,\s*")       # ", Hello" → "Hello"
MULTI_SPACE = re.compile(r"  +")              # collapse multiple spaces
TRAILING_COMMA_PERIOD = re.compile(r",\s*\.")  # ", ." → "."


DEFLUFF_SYSTEM_PROMPT = """\
You are a subtitle editor. Clean speech disfluencies from transcribed text.
Remove: filler words, false starts, self-corrections, unnecessary repetitions.
Preserve: all meaningful content, deliberate emphasis, proper nouns.
Rules: output one cleaned line per input line, same count. Do NOT rephrase or summarize.\
"""


def remove_fillers_regex(text: str) -> str:
    """Tier 1: Remove common filler words using regex.

    Handles um/uh/er/ah etc., fixes orphaned commas/spaces,
    and re-capitalizes the first character if needed.
    """
    if not text or not text.strip():
        return text

    cleaned = FILLER_PATTERN.sub("", text)

    # Fix punctuation artifacts
    cleaned = ORPHAN_COMMA.sub(",", cleaned)
    cleaned = TRAILING_COMMA_PERIOD.sub(".", cleaned)
    cleaned = LEADING_COMMA.sub("", cleaned)
    cleaned = MULTI_SPACE.sub(" ", cleaned)
    cleaned = cleaned.strip()

    # Re-capitalize first character if it was lowered by removal
    if cleaned and cleaned[0].islower() and (not text or text[0].isupper()):
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned


def _has_likely_repetitions(text: str) -> bool:
    """Heuristic: detect if text likely contains disfluent repetitions.

    Checks for:
    - Repeated 2+ word ngrams within proximity
    - Multiple comma-separated short fragments (false starts)
    """
    words = text.lower().split()
    if len(words) < 4:
        return False

    # Check for repeated bigrams
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    seen = {}
    for i, bg in enumerate(bigrams):
        if bg in seen and (i - seen[bg]) < 8:  # within 8 words
            return True
        seen[bg] = i

    # Check for many short comma-separated fragments (sign of false starts)
    fragments = text.split(",")
    if len(fragments) >= 3:
        short_fragments = sum(1 for f in fragments if len(f.strip().split()) <= 4)
        if short_fragments >= 3:
            return True

    return False


def _format_batch_prompt(texts: List[str]) -> str:
    """Format a batch of texts as numbered lines for LLM cleaning."""
    lines = [f"{i+1}. {text}" for i, text in enumerate(texts)]
    return "\n".join(lines)


def _parse_batch_response(response: str, expected_count: int) -> Optional[List[str]]:
    """Parse numbered lines from LLM response.

    Returns None if parsing fails or count doesn't match.
    """
    lines = response.strip().split("\n")
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove numbering prefix: "1. ", "1) ", etc.
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line)
        if cleaned:
            results.append(cleaned)

    if len(results) != expected_count:
        logger.warning(
            f"LLM returned {len(results)} lines, expected {expected_count}. "
            f"Falling back to originals."
        )
        return None

    return results


class DefluffWorker:
    """Two-tier speech disfluency removal."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.llm_model

    async def clean_segments_llm(
        self,
        texts: List[str],
        batch_size: int = 20,
    ) -> List[str]:
        """Tier 2: Clean complex repetitions using LLM.

        Batches texts into groups of `batch_size` for efficient processing.
        Falls back to originals if LLM fails or over-cleans.
        """
        from openai import AsyncOpenAI

        if settings.is_azure:
            from openai import AsyncAzureOpenAI
            client = AsyncAzureOpenAI(
                api_key=settings.llm_api_key,
                azure_endpoint=settings.llm_base_url,
                api_version=settings.azure_api_version,
            )
            model = settings.azure_deployment_name
        else:
            client = AsyncOpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )
            model = self.model

        results = list(texts)  # copy originals as fallback

        for batch_start in range(0, len(texts), batch_size):
            batch = texts[batch_start : batch_start + batch_size]
            batch_indices = list(range(batch_start, batch_start + len(batch)))

            # Only send segments that have likely repetitions
            to_clean = []
            to_clean_indices = []
            for idx, text in zip(batch_indices, batch):
                if _has_likely_repetitions(text):
                    to_clean.append(text)
                    to_clean_indices.append(idx)

            if not to_clean:
                continue

            prompt = _format_batch_prompt(to_clean)

            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": DEFLUFF_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=4096,
                )

                content = response.choices[0].message.content
                if not content:
                    continue

                parsed = _parse_batch_response(content, len(to_clean))
                if parsed is None:
                    continue

                # Apply results with safety check
                for idx, original, cleaned in zip(to_clean_indices, to_clean, parsed):
                    if len(cleaned) < len(original) * 0.4:
                        # Over-cleaning protection: keep original
                        logger.warning(
                            f"Defluff over-cleaned segment {idx}: "
                            f"{len(cleaned)}/{len(original)} chars. Keeping original."
                        )
                        continue
                    results[idx] = cleaned

            except Exception as e:
                logger.warning(f"LLM defluff batch failed: {e}. Keeping originals.")
                continue

        return results

    async def clean_transcript(
        self,
        transcript: DiarizedTranscript,
    ) -> DiarizedTranscript:
        """Clean disfluencies from a full diarized transcript.

        Pipeline entry point. Applies regex tier first, then LLM tier.
        Returns a new DiarizedTranscript with cleaned text.
        """
        if not transcript.segments:
            return transcript

        # Tier 1: Regex cleaning
        texts = [remove_fillers_regex(seg.text) for seg in transcript.segments]

        # Tier 2: LLM cleaning for complex repetitions
        texts = await self.clean_segments_llm(texts)

        # Build new transcript with cleaned text
        cleaned_segments = []
        changed = 0
        for seg, new_text in zip(transcript.segments, texts):
            if new_text != seg.text:
                changed += 1
            cleaned_segments.append(
                DiarizedSegment(
                    start=seg.start,
                    end=seg.end,
                    text=new_text,
                    speaker=seg.speaker,
                )
            )

        logger.info(
            f"Defluff: cleaned {changed}/{len(transcript.segments)} segments"
        )

        return DiarizedTranscript(
            language=transcript.language,
            num_speakers=transcript.num_speakers,
            segments=cleaned_segments,
        )

    async def clean_texts(self, texts: List[str]) -> List[str]:
        """Clean disfluencies from a list of text strings.

        Review UI entry point. Applies regex tier first, then LLM tier.
        """
        if not texts:
            return texts

        # Tier 1: Regex cleaning
        cleaned = [remove_fillers_regex(t) for t in texts]

        # Tier 2: LLM cleaning
        cleaned = await self.clean_segments_llm(cleaned)

        return cleaned
