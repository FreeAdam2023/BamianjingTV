"""Translation worker using OpenAI API."""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from app.config import settings
from app.models.transcript import (
    DiarizedSegment,
    DiarizedTranscript,
    TranslatedSegment,
    TranslatedTranscript,
)


# Language-specific translation prompts
TRANSLATION_PROMPTS: Dict[str, str] = {
    "zh-TW": """你是一位專業的視頻配音翻譯專家。你的任務是將英文訪談/演講內容翻譯成自然流暢的繁體中文。

翻譯要求：
1. 使用繁體中文：所有輸出必須是繁體中文字
2. 口語化：翻譯結果要適合朗讀和配音，不要書面語
3. 自然流暢：符合中文表達習慣，不要逐字翻譯
4. 保持語氣：保留原文的情感和語氣（興奮、嚴肅、幽默等）
5. 適當意譯：可以調整句子結構，讓中文更自然
6. 簡潔明了：配音需要清晰，避免過長的從句

只返回翻譯後的繁體中文文本，不要添加任何解釋或標註。""",

    "zh-CN": """你是一位专业的视频配音翻译专家。你的任务是将英文访谈/演讲内容翻译成自然流畅的简体中文。

翻译要求：
1. 使用简体中文：所有输出必须是简体中文字
2. 口语化：翻译结果要适合朗读和配音，不要书面语
3. 自然流畅：符合中文表达习惯，不要逐字翻译
4. 保持语气：保留原文的情感和语气（兴奋、严肃、幽默等）
5. 适当意译：可以调整句子结构，让中文更自然
6. 简洁明了：配音需要清晰，避免过长的从句

只返回翻译后的简体中文文本，不要添加任何解释或标注。""",

    "ja": """You are a professional video dubbing translator. Your task is to translate English interview/speech content into natural, fluent Japanese.

Translation requirements:
1. Use natural Japanese: Output must be in natural Japanese
2. Conversational: Translation should be suitable for voice-over, not formal written style
3. Natural flow: Follow Japanese expression habits, don't translate word-by-word
4. Preserve tone: Keep the original emotion and tone (excitement, seriousness, humor, etc.)
5. Appropriate interpretation: Adjust sentence structure to make Japanese more natural
6. Clear and concise: Voice-over needs clarity, avoid overly long clauses

Only return the translated Japanese text, do not add any explanations or annotations.""",

    "ko": """You are a professional video dubbing translator. Your task is to translate English interview/speech content into natural, fluent Korean.

Translation requirements:
1. Use natural Korean: Output must be in natural Korean
2. Conversational: Translation should be suitable for voice-over, not formal written style
3. Natural flow: Follow Korean expression habits, don't translate word-by-word
4. Preserve tone: Keep the original emotion and tone (excitement, seriousness, humor, etc.)
5. Appropriate interpretation: Adjust sentence structure to make Korean more natural
6. Clear and concise: Voice-over needs clarity, avoid overly long clauses

Only return the translated Korean text, do not add any explanations or annotations.""",

    "es": """You are a professional video dubbing translator. Your task is to translate English interview/speech content into natural, fluent Spanish.

Translation requirements:
1. Use natural Spanish: Output must be in natural Spanish
2. Conversational: Translation should be suitable for voice-over, not formal written style
3. Natural flow: Follow Spanish expression habits, don't translate word-by-word
4. Preserve tone: Keep the original emotion and tone (excitement, seriousness, humor, etc.)
5. Appropriate interpretation: Adjust sentence structure to make Spanish more natural
6. Clear and concise: Voice-over needs clarity, avoid overly long clauses

Only return the translated Spanish text, do not add any explanations or annotations.""",

    "fr": """You are a professional video dubbing translator. Your task is to translate English interview/speech content into natural, fluent French.

Translation requirements:
1. Use natural French: Output must be in natural French
2. Conversational: Translation should be suitable for voice-over, not formal written style
3. Natural flow: Follow French expression habits, don't translate word-by-word
4. Preserve tone: Keep the original emotion and tone (excitement, seriousness, humor, etc.)
5. Appropriate interpretation: Adjust sentence structure to make French more natural
6. Clear and concise: Voice-over needs clarity, avoid overly long clauses

Only return the translated French text, do not add any explanations or annotations.""",

    "de": """You are a professional video dubbing translator. Your task is to translate English interview/speech content into natural, fluent German.

Translation requirements:
1. Use natural German: Output must be in natural German
2. Conversational: Translation should be suitable for voice-over, not formal written style
3. Natural flow: Follow German expression habits, don't translate word-by-word
4. Preserve tone: Keep the original emotion and tone (excitement, seriousness, humor, etc.)
5. Appropriate interpretation: Adjust sentence structure to make German more natural
6. Clear and concise: Voice-over needs clarity, avoid overly long clauses

Only return the translated German text, do not add any explanations or annotations.""",
}

# Default prompt for unsupported languages
DEFAULT_TRANSLATION_PROMPT = """You are a professional video dubbing translator. Your task is to translate English interview/speech content into natural, fluent {language}.

Translation requirements:
1. Conversational: Translation should be suitable for voice-over, not formal written style
2. Natural flow: Follow target language expression habits, don't translate word-by-word
3. Preserve tone: Keep the original emotion and tone (excitement, seriousness, humor, etc.)
4. Appropriate interpretation: Adjust sentence structure to make it more natural
5. Clear and concise: Voice-over needs clarity, avoid overly long clauses

Only return the translated text, do not add any explanations or annotations."""

# Language display names
SUPPORTED_LANGUAGES = {
    "zh-TW": "繁體中文 (Traditional Chinese)",
    "zh-CN": "简体中文 (Simplified Chinese)",
    "ja": "日本語 (Japanese)",
    "ko": "한국어 (Korean)",
    "es": "Español (Spanish)",
    "fr": "Français (French)",
    "de": "Deutsch (German)",
}


class TranslationWorker:
    """Worker for translating transcripts using LLM API (OpenAI, Grok, Azure, etc.)."""

    def __init__(self):
        """Initialize translation worker."""
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        self.client = None

    def _get_translation_prompt(self, target_language: str = "zh-TW") -> str:
        """Get the translation prompt for the target language.

        Args:
            target_language: Target language code (default: zh-TW for Traditional Chinese)
                           Supported: zh-TW, zh-CN, ja, ko, es, fr, de
        """
        if target_language in TRANSLATION_PROMPTS:
            return TRANSLATION_PROMPTS[target_language]
        else:
            # Use default prompt with language name
            return DEFAULT_TRANSLATION_PROMPT.format(language=target_language)

    def _get_client(self):
        """Get or create LLM client."""
        if self.client is None:
            if not self.api_key:
                raise ValueError(
                    "LLM API key required. Set LLM_API_KEY environment variable."
                )

            if settings.is_azure:
                from openai import AsyncAzureOpenAI

                # Extract resource URL from base_url
                # e.g., https://xxx.openai.azure.com/openai/deployments/gpt-4.1-mini
                azure_endpoint = self.base_url.split("/openai/")[0]
                self.client = AsyncAzureOpenAI(
                    api_key=self.api_key,
                    api_version=settings.azure_api_version,
                    azure_endpoint=azure_endpoint,
                )
            else:
                from openai import AsyncOpenAI

                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )

        return self.client

    async def translate_text(
        self,
        text: str,
        target_language: str = "zh-TW",
        max_retries: int = 3,
        timeout: int = 30,
    ) -> str:
        """Translate a single text segment with timeout and retry.

        Args:
            text: Text to translate
            target_language: Target language code (default: zh-TW)
            max_retries: Number of retries on failure
            timeout: Timeout in seconds
        """
        from openai import BadRequestError

        client = self._get_client()
        system_prompt = self._get_translation_prompt(target_language)

        # Use Azure deployment name for Azure, model name for others (OpenAI, Grok, etc.)
        model_or_deployment = (
            settings.azure_deployment_name if settings.is_azure else self.model
        )

        for attempt in range(max_retries):
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=model_or_deployment,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text},
                        ],
                        temperature=0.3,
                    ),
                    timeout=timeout,
                )

                # Handle content filtering (Azure returns content=None when filtered)
                content = response.choices[0].message.content
                if content is None:
                    finish_reason = response.choices[0].finish_reason
                    if finish_reason == "content_filter":
                        logger.warning(f"Output filtered by Azure, returning original: {text[:50]}...")
                        return text  # Return original text if filtered
                    else:
                        logger.warning(f"Empty response from API (finish_reason={finish_reason})")
                        return text

                return content.strip()

            except BadRequestError as e:
                # Azure content filter blocks the input - don't retry, just return original
                error_str = str(e)
                if "content_filter" in error_str or "content management policy" in error_str:
                    logger.warning(f"Input filtered by Azure content policy, returning original: {text[:50]}...")
                    return text
                # Other bad request errors - also don't retry
                logger.warning(f"BadRequestError: {e}, returning original text")
                return text

            except asyncio.TimeoutError:
                logger.warning(f"Translation timeout (attempt {attempt + 1}/{max_retries}): {text[:50]}...")
                if attempt == max_retries - 1:
                    logger.error(f"Translation failed after {max_retries} attempts, returning original text")
                    return text
                await asyncio.sleep(1)  # Wait before retry

            except Exception as e:
                logger.warning(f"Translation error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Translation failed after {max_retries} attempts, returning original text")
                    return text
                await asyncio.sleep(1)  # Wait before retry

        return text  # Fallback

    async def translate_transcript(
        self,
        transcript: DiarizedTranscript,
        target_language: str = "zh-TW",
        batch_size: int = 10,
    ) -> TranslatedTranscript:
        """
        Translate all segments in a diarized transcript.

        Args:
            transcript: Diarized transcript to translate
            target_language: Target language code (default: zh-TW for Traditional Chinese)
            batch_size: Number of segments to translate concurrently

        Returns:
            TranslatedTranscript with translations
        """
        logger.info(f"Translating {len(transcript.segments)} segments to {target_language}...")

        translated_segments: List[TranslatedSegment] = []

        # Process in batches to avoid rate limits
        for i in range(0, len(transcript.segments), batch_size):
            batch = transcript.segments[i : i + batch_size]

            # Translate batch concurrently with error handling
            tasks = [self.translate_text(seg.text, target_language) for seg in batch]
            try:
                translations = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Batch translation failed: {e}")
                # Fall back to original text for this batch
                translations = [seg.text for seg in batch]

            # Create translated segments, handling any exceptions
            for seg, translation in zip(batch, translations):
                if isinstance(translation, Exception):
                    logger.warning(f"Segment translation failed, using original: {translation}")
                    translation = seg.text

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

            # Delay between batches to respect rate limits (Azure: 60 RPM for gpt-4)
            if i + batch_size < len(transcript.segments):
                await asyncio.sleep(1.0)

        return TranslatedTranscript(
            source_language=transcript.language,
            target_language=target_language,
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
