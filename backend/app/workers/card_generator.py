"""Card generator worker for fetching word and entity data from TomTrove API.

Uses TomTrove's dictionary and entity services for high-quality card data.
"""

import asyncio
from typing import List, Optional
import httpx
from loguru import logger

from app.config import settings
from app.models.card import (
    WordCard,
    EntityCard,
    EntityType,
    Pronunciation,
    WordSense,
    EntityLocalization,
)
from app.services.card_cache import CardCache


class CardGeneratorWorker:
    """Worker for generating word and entity cards from TomTrove API.

    APIs used:
    - TomTrove Dictionary API: /dictionary/{word}
    - TomTrove Entity API: /entities/recognize, /entities/details
    """

    def __init__(self, card_cache: Optional[CardCache] = None):
        """Initialize card generator.

        Args:
            card_cache: Optional card cache for storing results.
        """
        self.cache = card_cache or CardCache()
        self.http_client: Optional[httpx.AsyncClient] = None

        # TomTrove API settings
        self.tomtrove_url = settings.tomtrove_api_url
        self.tomtrove_key = settings.tomtrove_api_key

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with TomTrove auth headers."""
        if self.http_client is None or self.http_client.is_closed:
            headers = {}
            if self.tomtrove_key:
                headers["X-API-Key"] = self.tomtrove_key
            self.http_client = httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
            )
        return self.http_client

    async def close(self):
        """Close HTTP client."""
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()

    def _is_tomtrove_available(self) -> bool:
        """Check if TomTrove API is configured."""
        return bool(self.tomtrove_url and self.tomtrove_key)

    # ============ Word Card Generation ============

    async def get_word_card(
        self,
        word: str,
        use_cache: bool = True,
        target_lang: Optional[str] = None,
    ) -> Optional[WordCard]:
        """Get word card from TomTrove API.

        Args:
            word: The word to look up.
            use_cache: Whether to use cache.
            target_lang: Target language for translations (zh-TW, zh-CN, zh-Hans, zh-Hant).

        Returns:
            WordCard or None if not found.
        """
        word = word.lower().strip()

        # Normalize language code for TomTrove
        tomtrove_lang = self._normalize_lang_for_tomtrove(target_lang)

        # Include language in cache key
        cache_key = f"{word}:{tomtrove_lang}" if tomtrove_lang else word

        # Check cache first
        if use_cache:
            cached = self.cache.get_word_card(cache_key)
            if cached:
                logger.debug(f"Word card cache hit: {word}")
                return cached

        # Fetch from TomTrove API
        card = await self._fetch_word_from_tomtrove(word, tomtrove_lang)

        # Cache result
        if card and use_cache:
            self.cache.set_word_card(card, cache_key=cache_key)

        return card

    def _normalize_lang_for_tomtrove(self, lang: Optional[str]) -> str:
        """Normalize language code for TomTrove API.

        TomTrove uses: zh-Hans (simplified), zh-Hant (traditional)
        BamianjingTV uses: zh-TW (traditional), zh-CN (simplified)
        """
        if not lang:
            return "zh-Hant"  # Default to traditional Chinese

        lang_map = {
            "zh-TW": "zh-Hant",
            "zh-CN": "zh-Hans",
            "zh-tw": "zh-Hant",
            "zh-cn": "zh-Hans",
            "zh_TW": "zh-Hant",
            "zh_CN": "zh-Hans",
        }
        return lang_map.get(lang, lang)

    async def _fetch_word_from_tomtrove(
        self,
        word: str,
        target_lang: str = "zh-Hant",
    ) -> Optional[WordCard]:
        """Fetch word data from TomTrove Dictionary API.

        Args:
            word: Word to look up.
            target_lang: Target language for translations.

        Returns:
            WordCard or None.
        """
        if not self._is_tomtrove_available():
            logger.warning("TomTrove API not configured, falling back to free dictionary")
            return await self._fetch_word_from_free_dictionary(word)

        url = f"{self.tomtrove_url}/dictionary/{word}"
        params = {
            "from_lang": "en",
            "to_langs": target_lang,
        }

        try:
            client = await self._get_client()
            response = await client.get(url, params=params)

            if response.status_code == 404:
                logger.debug(f"Word not found in TomTrove: {word}")
                return None

            if response.status_code != 200:
                logger.warning(f"TomTrove API error for {word}: {response.status_code}")
                return None

            data = response.json()

            # Parse TomTrove response into WordCard
            return self._parse_tomtrove_word_response(word, data, target_lang)

        except Exception as e:
            logger.error(f"Error fetching word from TomTrove {word}: {e}")
            return None

    def _parse_tomtrove_word_response(
        self,
        word: str,
        data: dict,
        target_lang: str,
    ) -> Optional[WordCard]:
        """Parse TomTrove dictionary response into WordCard.

        TomTrove response format:
        {
            "word": "hello",
            "source_lang": "en",
            "phonetic": "/həˈloʊ/",
            "audio_url": "https://...",
            "translations": {
                "zh-Hant": {
                    "translations": [{"text": "你好", "pos": "interjection"}],
                    "examples": [{"source": "Hello!", "target": "你好！"}]
                }
            },
            "synonyms": [...],
            "antonyms": [...]
        }
        """
        try:
            # Extract pronunciation
            pronunciations = []
            if data.get("phonetic"):
                pron = Pronunciation(
                    ipa=data["phonetic"],
                    audio_url=data.get("audio_url"),
                    region="us",
                )
                pronunciations.append(pron)

            # Extract senses from translations
            senses = []
            translations = data.get("translations", {})
            lang_data = translations.get(target_lang, {})

            trans_list = lang_data.get("translations", [])
            examples_list = lang_data.get("examples", [])

            # Group translations by part of speech
            pos_groups = {}
            for trans in trans_list:
                pos = trans.get("pos", "other") or "other"
                if pos not in pos_groups:
                    pos_groups[pos] = []
                pos_groups[pos].append(trans.get("text", ""))

            # Create senses
            example_idx = 0
            for pos, trans_texts in pos_groups.items():
                for trans_text in trans_texts:
                    # Get example if available
                    example_en = ""
                    example_zh = ""
                    if example_idx < len(examples_list):
                        ex = examples_list[example_idx]
                        example_en = ex.get("source", "")
                        example_zh = ex.get("target", "")
                        example_idx += 1

                    sense = WordSense(
                        part_of_speech=pos,
                        definition=trans_text,  # Use Chinese as main definition
                        definition_zh=trans_text,
                        examples=[example_en] if example_en else [],
                        examples_zh=[example_zh] if example_zh else [],
                        synonyms=data.get("synonyms", [])[:5],
                        antonyms=data.get("antonyms", [])[:5],
                    )
                    senses.append(sense)

            if not senses:
                # Fallback: create a simple sense if we have any translation
                for trans in trans_list:
                    sense = WordSense(
                        part_of_speech=trans.get("pos", "other") or "other",
                        definition=trans.get("text", ""),
                        definition_zh=trans.get("text", ""),
                    )
                    senses.append(sense)

            if not senses:
                logger.debug(f"No translations found for: {word}")
                return None

            card = WordCard(
                word=word,
                lemma=data.get("word", word),
                pronunciations=pronunciations,
                senses=senses[:10],
                source="tomtrove",
            )

            logger.debug(f"Fetched word card from TomTrove: {word} ({len(senses)} senses)")
            return card

        except Exception as e:
            logger.error(f"Error parsing TomTrove word response for {word}: {e}")
            return None

    async def _fetch_word_from_free_dictionary(self, word: str) -> Optional[WordCard]:
        """Fallback: Fetch word data from Free Dictionary API.

        Args:
            word: Word to look up.

        Returns:
            WordCard or None.
        """
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

        try:
            client = await self._get_client()
            response = await client.get(url)

            if response.status_code == 404:
                logger.debug(f"Word not found in dictionary: {word}")
                return None

            if response.status_code != 200:
                logger.warning(f"Dictionary API error for {word}: {response.status_code}")
                return None

            data = response.json()
            if not data or not isinstance(data, list):
                return None

            entry = data[0]

            # Extract pronunciations
            pronunciations = []
            for phonetic in entry.get("phonetics", []):
                if phonetic.get("text"):
                    pron = Pronunciation(
                        ipa=phonetic["text"],
                        audio_url=phonetic.get("audio"),
                        region="us" if "us" in phonetic.get("audio", "").lower() else "uk",
                    )
                    pronunciations.append(pron)

            # Extract senses/meanings
            senses = []
            for meaning in entry.get("meanings", []):
                pos = meaning.get("partOfSpeech", "other")
                for definition in meaning.get("definitions", []):
                    sense = WordSense(
                        part_of_speech=pos,
                        definition=definition.get("definition", ""),
                        examples=definition.get("example", []) if isinstance(definition.get("example"), list)
                                 else [definition.get("example")] if definition.get("example") else [],
                        synonyms=definition.get("synonyms", [])[:5],
                        antonyms=definition.get("antonyms", [])[:5],
                    )
                    senses.append(sense)

            if not senses:
                logger.debug(f"No definitions found for: {word}")
                return None

            lemma = entry.get("word", word)

            card = WordCard(
                word=word,
                lemma=lemma,
                pronunciations=pronunciations,
                senses=senses[:10],
                source="free_dictionary",
            )

            logger.debug(f"Fetched word card: {word} ({len(senses)} senses)")
            return card

        except Exception as e:
            logger.error(f"Error fetching word {word}: {e}")
            return None

    async def get_word_cards_batch(
        self,
        words: List[str],
        use_cache: bool = True,
        target_lang: Optional[str] = None,
        concurrency: int = 5,
    ) -> dict[str, Optional[WordCard]]:
        """Fetch multiple word cards with concurrency control.

        Args:
            words: List of words to look up.
            use_cache: Whether to use cache.
            target_lang: Target language for translations.
            concurrency: Max concurrent requests.

        Returns:
            Dict mapping words to cards (or None).
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_limit(word: str) -> tuple[str, Optional[WordCard]]:
            async with semaphore:
                card = await self.get_word_card(word, use_cache, target_lang)
                return word, card

        tasks = [fetch_with_limit(word) for word in words]
        results = await asyncio.gather(*tasks)

        return dict(results)

    # ============ Entity Card Generation ============

    async def get_entity_card(
        self,
        entity_id: str,
        use_cache: bool = True,
        target_lang: Optional[str] = None,
    ) -> Optional[EntityCard]:
        """Get entity card from TomTrove API.

        Args:
            entity_id: Wikidata QID (e.g., Q42).
            use_cache: Whether to use cache.
            target_lang: Target language for localization.

        Returns:
            EntityCard or None.
        """
        entity_id = entity_id.upper().strip()

        # Check cache first
        if use_cache:
            cached = self.cache.get_entity_card(entity_id)
            if cached:
                logger.debug(f"Entity card cache hit: {entity_id}")
                return cached

        # Fetch from TomTrove API
        card = await self._fetch_entity_from_tomtrove(entity_id, target_lang)

        # Cache result
        if card and use_cache:
            self.cache.set_entity_card(card)

        return card

    async def search_entity(self, query: str, lang: str = "en") -> Optional[str]:
        """Search for an entity by name and return its QID.

        Uses TomTrove's entity recognition API.

        Args:
            query: Search query (e.g., "Albert Einstein").
            lang: Language for search.

        Returns:
            Wikidata QID or None.
        """
        if not self._is_tomtrove_available():
            logger.warning("TomTrove API not configured for entity search")
            return await self._search_entity_wikidata(query, lang)

        url = f"{self.tomtrove_url}/entities/recognize"

        try:
            client = await self._get_client()
            response = await client.post(
                url,
                json={"text": query},
            )

            if response.status_code != 200:
                logger.warning(f"TomTrove entity search failed for '{query}': {response.status_code}")
                return await self._search_entity_wikidata(query, lang)

            data = response.json()

            if not data.get("success"):
                logger.warning(f"TomTrove entity search unsuccessful for '{query}'")
                return await self._search_entity_wikidata(query, lang)

            # Get first entity from results
            entities = data.get("data", {}).get("entities", [])
            if entities:
                entity_id = entities[0].get("entity_id")
                if entity_id:
                    logger.info(f"Found entity '{query}' -> {entity_id} (via TomTrove)")
                    return entity_id

            logger.debug(f"No entities found for '{query}' in TomTrove")
            return await self._search_entity_wikidata(query, lang)

        except Exception as e:
            logger.error(f"Error searching entity '{query}' via TomTrove: {e}")
            return await self._search_entity_wikidata(query, lang)

    async def _search_entity_wikidata(self, query: str, lang: str = "en") -> Optional[str]:
        """Fallback: Search entity via Wikidata API."""
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": lang,
            "format": "json",
            "limit": 1,
        }

        try:
            client = await self._get_client()
            response = await client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(f"Wikidata search failed for '{query}': {response.status_code}")
                return None

            data = response.json()
            results = data.get("search", [])

            if results:
                qid = results[0].get("id")
                logger.info(f"Found entity '{query}' -> {qid} (via Wikidata)")
                return qid

            return None

        except Exception as e:
            logger.error(f"Error searching entity '{query}' via Wikidata: {e}")
            return None

    async def _fetch_entity_from_tomtrove(
        self,
        entity_id: str,
        target_lang: Optional[str] = None,
    ) -> Optional[EntityCard]:
        """Fetch entity data from TomTrove API.

        Args:
            entity_id: Wikidata QID.
            target_lang: Target language for localization.

        Returns:
            EntityCard or None.
        """
        if not self._is_tomtrove_available():
            logger.warning("TomTrove API not configured, falling back to Wikidata")
            return await self._fetch_entity_from_wikidata(entity_id)

        url = f"{self.tomtrove_url}/entities/details"
        params = {"entity_id": entity_id}

        try:
            client = await self._get_client()
            response = await client.get(url, params=params)

            if response.status_code == 404:
                logger.debug(f"Entity not found in TomTrove: {entity_id}")
                return await self._fetch_entity_from_wikidata(entity_id)

            if response.status_code != 200:
                logger.warning(f"TomTrove entity API error for {entity_id}: {response.status_code}")
                return await self._fetch_entity_from_wikidata(entity_id)

            data = response.json()

            if not data.get("success"):
                logger.warning(f"TomTrove entity fetch unsuccessful for {entity_id}")
                return await self._fetch_entity_from_wikidata(entity_id)

            return self._parse_tomtrove_entity_response(entity_id, data, target_lang)

        except Exception as e:
            logger.error(f"Error fetching entity from TomTrove {entity_id}: {e}")
            return await self._fetch_entity_from_wikidata(entity_id)

    def _parse_tomtrove_entity_response(
        self,
        entity_id: str,
        data: dict,
        target_lang: Optional[str] = None,
    ) -> Optional[EntityCard]:
        """Parse TomTrove entity response into EntityCard.

        TomTrove response format:
        {
            "success": true,
            "data": {
                "resolution": {
                    "wikidata_id": "Q937",
                    "localizations": {
                        "zh_cn": {
                            "title": "阿尔伯特·爱因斯坦",
                            "description": "物理学家",
                            "url": "https://zh.wikipedia.org/wiki/...",
                            "thumbnail": "https://..."
                        },
                        "en": {...}
                    },
                    "images": [{"url": "..."}]
                }
            }
        }
        """
        try:
            resolution = data.get("data", {}).get("resolution", {})
            localizations_data = resolution.get("localizations", {})
            images = resolution.get("images", [])

            # Get English localization as base
            en_loc = localizations_data.get("en", {})
            name = en_loc.get("title", entity_id)
            description = en_loc.get("description", "")
            wikipedia_url = en_loc.get("url")

            # Get image URL
            image_url = None
            if images:
                image_url = images[0].get("url")
            if not image_url:
                image_url = en_loc.get("thumbnail")

            # Build localizations for Chinese
            localizations = {}
            for lang_key in ["zh_cn", "zh_tw", "zh-cn", "zh-tw", "zh"]:
                zh_loc = localizations_data.get(lang_key)
                if zh_loc:
                    localizations["zh"] = EntityLocalization(
                        name=zh_loc.get("title", name),
                        description=zh_loc.get("description"),
                    )
                    break

            # Infer entity type (TomTrove doesn't provide this directly)
            entity_type = EntityType.OTHER

            card = EntityCard(
                entity_id=entity_id,
                entity_type=entity_type,
                name=name,
                description=description,
                wikipedia_url=wikipedia_url,
                wikidata_url=f"https://www.wikidata.org/wiki/{entity_id}",
                image_url=image_url,
                localizations=localizations,
                source="tomtrove",
            )

            logger.debug(f"Fetched entity card from TomTrove: {entity_id} ({name})")
            return card

        except Exception as e:
            logger.error(f"Error parsing TomTrove entity response for {entity_id}: {e}")
            return None

    async def _fetch_entity_from_wikidata(self, entity_id: str) -> Optional[EntityCard]:
        """Fallback: Fetch entity data from Wikidata API."""
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "format": "json",
            "languages": "en|zh",
            "props": "labels|descriptions|claims|sitelinks",
        }

        try:
            client = await self._get_client()
            response = await client.get(url, params=params)

            if response.status_code != 200:
                logger.warning(f"Wikidata API error for {entity_id}: {response.status_code}")
                return None

            data = response.json()
            entities = data.get("entities", {})

            if entity_id not in entities or "missing" in entities.get(entity_id, {}):
                logger.debug(f"Entity not found: {entity_id}")
                return None

            entity = entities[entity_id]

            # Extract labels
            labels = entity.get("labels", {})
            name = labels.get("en", {}).get("value", entity_id)

            # Extract descriptions
            descriptions = entity.get("descriptions", {})
            description = descriptions.get("en", {}).get("value", "")

            # Extract claims for type-specific data
            claims = entity.get("claims", {})

            # Determine entity type
            entity_type = self._infer_entity_type(claims)

            # Extract image from P18
            image_url = None
            if "P18" in claims:
                image_name = claims["P18"][0].get("mainsnak", {}).get("datavalue", {}).get("value")
                if image_name:
                    image_name = image_name.replace(" ", "_")
                    image_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{image_name}?width=300"

            # Extract Wikipedia URL
            sitelinks = entity.get("sitelinks", {})
            wikipedia_url = None
            if "enwiki" in sitelinks:
                wiki_title = sitelinks["enwiki"].get("title", "").replace(" ", "_")
                wikipedia_url = f"https://en.wikipedia.org/wiki/{wiki_title}"

            # Build localizations
            localizations = {}
            if "zh" in labels or "zh" in descriptions:
                localizations["zh"] = EntityLocalization(
                    name=labels.get("zh", {}).get("value", name),
                    description=descriptions.get("zh", {}).get("value"),
                )

            # Extract type-specific fields
            birth_date = self._extract_date_claim(claims, "P569")
            death_date = self._extract_date_claim(claims, "P570")
            nationality = self._extract_item_label(claims, "P27")
            founded_date = self._extract_date_claim(claims, "P571")

            card = EntityCard(
                entity_id=entity_id,
                entity_type=entity_type,
                name=name,
                description=description,
                wikipedia_url=wikipedia_url,
                wikidata_url=f"https://www.wikidata.org/wiki/{entity_id}",
                image_url=image_url,
                birth_date=birth_date,
                death_date=death_date,
                nationality=nationality,
                founded_date=founded_date,
                localizations=localizations,
                source="wikidata",
            )

            logger.debug(f"Fetched entity card from Wikidata: {entity_id} ({name})")
            return card

        except Exception as e:
            logger.error(f"Error fetching entity {entity_id} from Wikidata: {e}")
            return None

    def _infer_entity_type(self, claims: dict) -> EntityType:
        """Infer entity type from Wikidata claims."""
        if "P31" not in claims:
            return EntityType.OTHER

        instance_of_ids = []
        for claim in claims["P31"]:
            qid = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if qid:
                instance_of_ids.append(qid)

        person_types = {"Q5"}
        place_types = {"Q515", "Q6256", "Q486972"}
        org_types = {"Q43229", "Q4830453", "Q783794"}
        work_types = {"Q11424", "Q7725634", "Q571"}
        event_types = {"Q1190554", "Q1656682"}

        for qid in instance_of_ids:
            if qid in person_types:
                return EntityType.PERSON
            if qid in place_types:
                return EntityType.PLACE
            if qid in org_types:
                return EntityType.ORGANIZATION
            if qid in work_types:
                return EntityType.WORK
            if qid in event_types:
                return EntityType.EVENT

        return EntityType.OTHER

    def _extract_date_claim(self, claims: dict, property_id: str) -> Optional[str]:
        """Extract a date from Wikidata claims."""
        if property_id not in claims:
            return None

        try:
            time_value = claims[property_id][0].get("mainsnak", {}).get("datavalue", {}).get("value", {})
            time_str = time_value.get("time", "")
            if time_str:
                return time_str[1:11]
        except (IndexError, KeyError):
            pass
        return None

    def _extract_item_label(self, claims: dict, property_id: str) -> Optional[str]:
        """Extract an item label from Wikidata claims."""
        if property_id not in claims:
            return None

        try:
            qid = claims[property_id][0].get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            return qid
        except (IndexError, KeyError):
            pass
        return None

    async def get_entity_cards_batch(
        self,
        entity_ids: List[str],
        use_cache: bool = True,
        target_lang: Optional[str] = None,
        concurrency: int = 3,
    ) -> dict[str, Optional[EntityCard]]:
        """Fetch multiple entity cards with concurrency control."""
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_limit(entity_id: str) -> tuple[str, Optional[EntityCard]]:
            async with semaphore:
                card = await self.get_entity_card(entity_id, use_cache, target_lang)
                return entity_id, card

        tasks = [fetch_with_limit(eid) for eid in entity_ids]
        results = await asyncio.gather(*tasks)

        return dict(results)
