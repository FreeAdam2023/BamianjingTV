"""Azure Translator service for subtitle translation.

Uses Azure Cognitive Services Translator API for fast, consistent translations.
Supports batch translation to maintain context across sentences.
"""

import asyncio
from typing import List, Optional, Tuple
import httpx
from loguru import logger

from app.config import settings


class AzureTranslator:
    """Azure Translator service for subtitle translation.

    Features:
    - Batch translation for context awareness
    - Support for Traditional/Simplified Chinese
    - Fast and cost-effective
    """

    def __init__(self):
        self.api_key = settings.azure_translator_key
        self.endpoint = settings.azure_translator_endpoint
        self.region = settings.azure_translator_region
        self.http_client: Optional[httpx.AsyncClient] = None

    def is_available(self) -> bool:
        """Check if Azure Translator is configured."""
        return bool(self.api_key and self.endpoint)

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(timeout=30.0)
        return self.http_client

    async def close(self):
        """Close HTTP client."""
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()

    async def translate_text(
        self,
        text: str,
        target_lang: str = "zh-Hans",
        source_lang: str = "en",
    ) -> Optional[str]:
        """Translate a single text.

        Args:
            text: Text to translate.
            target_lang: Target language (zh-Hans for Simplified, zh-Hant for Traditional).
            source_lang: Source language.

        Returns:
            Translated text or None if failed.
        """
        results = await self.translate_batch([text], target_lang, source_lang)
        return results[0] if results else None

    async def translate_batch(
        self,
        texts: List[str],
        target_lang: str = "zh-Hans",
        source_lang: str = "en",
    ) -> List[Optional[str]]:
        """Translate multiple texts in batch for context awareness.

        Azure Translator considers context when translating batches,
        resulting in more coherent translations for dialogues.

        Args:
            texts: List of texts to translate.
            target_lang: Target language (zh-Hans for Simplified, zh-Hant for Traditional).
            source_lang: Source language.

        Returns:
            List of translated texts (None for failed items).
        """
        if not self.is_available():
            logger.warning("Azure Translator not configured")
            return [None] * len(texts)

        if not texts:
            return []

        # Azure Translator API endpoint
        # Support both global endpoint and resource-specific endpoint
        if "cognitiveservices.azure.com" in self.endpoint:
            # Resource-specific endpoint (multi-service cognitive services)
            url = f"{self.endpoint.rstrip('/')}/translator/text/v3.0/translate"
        elif self.endpoint.endswith("/translate"):
            url = self.endpoint
        else:
            # Global endpoint
            url = f"{self.endpoint.rstrip('/')}/translate"

        # Map language codes
        to_lang = self._map_language_code(target_lang)
        from_lang = self._map_language_code(source_lang)

        params = {
            "api-version": "3.0",
            "from": from_lang,
            "to": to_lang,
        }

        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/json",
        }

        # Add region header only for global endpoint
        if "api.cognitive.microsofttranslator.com" in self.endpoint:
            headers["Ocp-Apim-Subscription-Region"] = self.region

        # Prepare request body
        body = [{"Text": text} for text in texts]

        try:
            client = await self._get_client()
            response = await client.post(
                url,
                params=params,
                headers=headers,
                json=body,
            )

            if response.status_code != 200:
                logger.error(f"Azure Translator error: {response.status_code} - {response.text}")
                return [None] * len(texts)

            data = response.json()

            # Extract translations
            results = []
            for item in data:
                translations = item.get("translations", [])
                if translations:
                    results.append(translations[0].get("text"))
                else:
                    results.append(None)

            logger.debug(f"Azure Translator: translated {len(texts)} texts to {to_lang}")
            return results

        except Exception as e:
            logger.error(f"Azure Translator error: {e}")
            return [None] * len(texts)

    async def translate_segments(
        self,
        segments: List[dict],
        target_lang: str = "zh-Hans",
        source_lang: str = "en",
        batch_size: int = 50,
    ) -> List[dict]:
        """Translate subtitle segments with context awareness.

        Translates in batches to maintain context while respecting API limits.

        Args:
            segments: List of segment dicts with 'en' field.
            target_lang: Target language.
            source_lang: Source language.
            batch_size: Number of segments per batch (max 100 for Azure).

        Returns:
            Segments with 'zh' field populated.
        """
        if not segments:
            return segments

        # Extract texts
        texts = [seg.get("en", "") or seg.get("text", "") for seg in segments]

        # Translate in batches
        all_translations = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            translations = await self.translate_batch(batch, target_lang, source_lang)
            all_translations.extend(translations)

            # Small delay between batches to avoid rate limiting
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)

        # Apply translations to segments
        for seg, translation in zip(segments, all_translations):
            if translation:
                seg["zh"] = translation

        logger.info(f"Azure Translator: translated {len(segments)} segments")
        return segments

    def _map_language_code(self, lang: str) -> str:
        """Map language codes to Azure Translator format.

        Azure uses:
        - zh-Hant: Traditional Chinese
        - zh-Hans: Simplified Chinese
        """
        lang_map = {
            "zh-TW": "zh-Hant",
            "zh-CN": "zh-Hans",
            "zh-tw": "zh-Hant",
            "zh-cn": "zh-Hans",
            "zh_TW": "zh-Hant",
            "zh_CN": "zh-Hans",
            "zh": "zh-Hans",  # Default to Simplified
        }
        return lang_map.get(lang, lang)

    async def detect_language(self, text: str) -> Optional[str]:
        """Detect the language of text.

        Args:
            text: Text to detect.

        Returns:
            Language code or None.
        """
        if not self.is_available():
            return None

        url = f"{self.endpoint}/detect"
        params = {"api-version": "3.0"}
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json",
        }
        body = [{"Text": text}]

        try:
            client = await self._get_client()
            response = await client.post(url, params=params, headers=headers, json=body)

            if response.status_code != 200:
                return None

            data = response.json()
            if data:
                return data[0].get("language")

        except Exception as e:
            logger.error(f"Language detection error: {e}")

        return None


# Global instance
azure_translator = AzureTranslator()
