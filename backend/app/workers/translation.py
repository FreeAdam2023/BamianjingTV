"""Translation worker using OpenAI API."""

import asyncio
from pathlib import Path
from typing import List
from loguru import logger

from app.config import settings
from app.models.transcript import (
    DiarizedSegment,
    DiarizedTranscript,
    TranslatedSegment,
    TranslatedTranscript,
)


TRANSLATION_SYSTEM_PROMPT = """你是一位专业的视频配音翻译专家。你的任务是将英文访谈/演讲内容翻译成自然流畅的中文。

翻译要求：
1. 口语化：翻译结果要适合朗读和配音，不要书面语
2. 自然流畅：符合中文表达习惯，不要逐字翻译
3. 保持语气：保留原文的情感和语气（兴奋、严肃、幽默等）
4. 适当意译：可以调整句子结构，让中文更自然
5. 简洁明了：配音需要清晰，避免过长的从句

只返回翻译后的中文文本，不要添加任何解释或标注。"""


class TranslationWorker:
    """Worker for translating transcripts using OpenAI API."""

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = settings.openai_base_url
        self.model = settings.translation_model
        self.client = None

    def _get_client(self):
        """Get or create OpenAI client."""
        if self.client is None:
            if not self.api_key:
                raise ValueError(
                    "OpenAI API key required. Set OPENAI_API_KEY environment variable."
                )

            if settings.is_azure_openai:
                from openai import AsyncAzureOpenAI

                # Extract resource URL from base_url
                # e.g., https://xxx.openai.azure.com/openai/deployments/gpt-4.1-mini
                azure_endpoint = self.base_url.split("/openai/")[0]
                self.client = AsyncAzureOpenAI(
                    api_key=self.api_key,
                    api_version=settings.openai_api_version,
                    azure_endpoint=azure_endpoint,
                )
            else:
                from openai import AsyncOpenAI

                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )

        return self.client

    async def translate_text(self, text: str) -> str:
        """Translate a single text segment."""
        client = self._get_client()

        # Use Azure deployment name for Azure, model name for OpenAI
        model_or_deployment = (
            settings.azure_deployment_name if settings.is_azure_openai else self.model
        )

        response = await client.chat.completions.create(
            model=model_or_deployment,
            messages=[
                {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.3,
        )

        # Handle content filtering (Azure returns content=None when filtered)
        content = response.choices[0].message.content
        if content is None:
            finish_reason = response.choices[0].finish_reason
            if finish_reason == "content_filter":
                logger.warning(f"Content filtered by Azure, returning original text: {text[:50]}...")
                return text  # Return original text if filtered
            else:
                logger.warning(f"Empty response from API (finish_reason={finish_reason})")
                return text

        return content.strip()

    async def translate_transcript(
        self,
        transcript: DiarizedTranscript,
        batch_size: int = 10,
    ) -> TranslatedTranscript:
        """
        Translate all segments in a diarized transcript.

        Args:
            transcript: Diarized transcript to translate
            batch_size: Number of segments to translate concurrently

        Returns:
            TranslatedTranscript with Chinese translations
        """
        logger.info(f"Translating {len(transcript.segments)} segments...")

        translated_segments: List[TranslatedSegment] = []

        # Process in batches to avoid rate limits
        for i in range(0, len(transcript.segments), batch_size):
            batch = transcript.segments[i : i + batch_size]

            # Translate batch concurrently
            tasks = [self.translate_text(seg.text) for seg in batch]
            translations = await asyncio.gather(*tasks)

            # Create translated segments
            for seg, translation in zip(batch, translations):
                translated_segments.append(
                    TranslatedSegment(
                        start=seg.start,
                        end=seg.end,
                        text=seg.text,
                        speaker=seg.speaker,
                        translation=translation,
                    )
                )

            logger.info(
                f"Translated {min(i + batch_size, len(transcript.segments))}"
                f"/{len(transcript.segments)} segments"
            )

            # Small delay between batches to respect rate limits
            if i + batch_size < len(transcript.segments):
                await asyncio.sleep(0.5)

        return TranslatedTranscript(
            source_language=transcript.language,
            target_language="zh",
            num_speakers=transcript.num_speakers,
            segments=translated_segments,
        )

    async def save_translation(
        self,
        transcript: TranslatedTranscript,
        output_path: Path,
    ) -> None:
        """Save translated transcript to JSON file."""
        import json

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(transcript.model_dump(), f, ensure_ascii=False, indent=2)

        logger.info(f"Translation saved to: {output_path}")
