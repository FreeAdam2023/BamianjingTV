"""Card generator worker for fetching word and entity data from APIs."""

import asyncio
from typing import List, Optional
import httpx
from loguru import logger

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
    """Worker for generating word and entity cards from external APIs.

    APIs used:
    - Free Dictionary API: https://dictionaryapi.dev/
    - Wikidata API: https://www.wikidata.org/wiki/Wikidata:Data_access
    """

    def __init__(self, card_cache: Optional[CardCache] = None):
        """Initialize card generator.

        Args:
            card_cache: Optional card cache for storing results.
        """
        self.cache = card_cache or CardCache()
        self.http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(timeout=30.0)
        return self.http_client

    async def close(self):
        """Close HTTP client."""
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()

    # ============ Word Card Generation ============

    async def get_word_card(self, word: str, use_cache: bool = True) -> Optional[WordCard]:
        """Get word card, from cache or API.

        Args:
            word: The word to look up.
            use_cache: Whether to use cache.

        Returns:
            WordCard or None if not found.
        """
        word = word.lower().strip()

        # Check cache first
        if use_cache:
            cached = self.cache.get_word_card(word)
            if cached:
                return cached

        # Fetch from API
        card = await self._fetch_word_from_free_dictionary(word)

        # Cache result
        if card and use_cache:
            self.cache.set_word_card(card)

        return card

    async def _fetch_word_from_free_dictionary(self, word: str) -> Optional[WordCard]:
        """Fetch word data from Free Dictionary API.

        API docs: https://dictionaryapi.dev/

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
                        synonyms=definition.get("synonyms", [])[:5],  # Limit synonyms
                        antonyms=definition.get("antonyms", [])[:5],
                    )
                    senses.append(sense)

            if not senses:
                logger.debug(f"No definitions found for: {word}")
                return None

            # Get lemma (base form) - use the word itself for now
            lemma = entry.get("word", word)

            card = WordCard(
                word=word,
                lemma=lemma,
                pronunciations=pronunciations,
                senses=senses[:10],  # Limit to 10 senses
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
        concurrency: int = 5,
    ) -> dict[str, Optional[WordCard]]:
        """Fetch multiple word cards with concurrency control.

        Args:
            words: List of words to look up.
            use_cache: Whether to use cache.
            concurrency: Max concurrent requests.

        Returns:
            Dict mapping words to cards (or None).
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_limit(word: str) -> tuple[str, Optional[WordCard]]:
            async with semaphore:
                card = await self.get_word_card(word, use_cache)
                return word, card

        tasks = [fetch_with_limit(word) for word in words]
        results = await asyncio.gather(*tasks)

        return dict(results)

    # ============ Entity Card Generation ============

    async def get_entity_card(
        self,
        entity_id: str,
        use_cache: bool = True,
    ) -> Optional[EntityCard]:
        """Get entity card, from cache or Wikidata API.

        Args:
            entity_id: Wikidata QID (e.g., Q42).
            use_cache: Whether to use cache.

        Returns:
            EntityCard or None.
        """
        entity_id = entity_id.upper().strip()

        # Check cache first
        if use_cache:
            cached = self.cache.get_entity_card(entity_id)
            if cached:
                return cached

        # Fetch from Wikidata
        card = await self._fetch_entity_from_wikidata(entity_id)

        # Cache result
        if card and use_cache:
            self.cache.set_entity_card(card)

        return card

    async def search_entity(self, query: str, lang: str = "en") -> Optional[str]:
        """Search for an entity by name and return its QID.

        Args:
            query: Search query (e.g., "Albert Einstein").
            lang: Language for search.

        Returns:
            Wikidata QID or None.
        """
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

            logger.info(f"Wikidata search for '{query}': status={response.status_code}")

            if response.status_code != 200:
                logger.warning(f"Wikidata search failed for '{query}': status={response.status_code}, body={response.text[:200]}")
                return None

            data = response.json()
            results = data.get("search", [])

            logger.info(f"Wikidata search results for '{query}': {len(results)} results, keys={list(data.keys())}")

            if results:
                qid = results[0].get("id")
                logger.info(f"Found entity '{query}' -> {qid}")
                return qid

            logger.warning(f"No Wikidata results for '{query}', response: {data}")
            return None

        except Exception as e:
            logger.error(f"Error searching entity '{query}': {e}")
            return None

    async def _fetch_entity_from_wikidata(self, entity_id: str) -> Optional[EntityCard]:
        """Fetch entity data from Wikidata API.

        Args:
            entity_id: Wikidata QID.

        Returns:
            EntityCard or None.
        """
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

            # Determine entity type from instance of (P31)
            entity_type = self._infer_entity_type(claims)

            # Extract image from P18
            image_url = None
            if "P18" in claims:
                image_name = claims["P18"][0].get("mainsnak", {}).get("datavalue", {}).get("value")
                if image_name:
                    # Convert to Wikimedia Commons URL
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
            birth_date = self._extract_date_claim(claims, "P569")  # Date of birth
            death_date = self._extract_date_claim(claims, "P570")  # Date of death
            nationality = self._extract_item_label(claims, "P27")  # Country of citizenship
            founded_date = self._extract_date_claim(claims, "P571")  # Inception

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

            logger.debug(f"Fetched entity card: {entity_id} ({name})")
            return card

        except Exception as e:
            logger.error(f"Error fetching entity {entity_id}: {e}")
            return None

    def _infer_entity_type(self, claims: dict) -> EntityType:
        """Infer entity type from Wikidata claims.

        Args:
            claims: Wikidata claims dict.

        Returns:
            EntityType enum value.
        """
        # P31 = instance of
        if "P31" not in claims:
            return EntityType.OTHER

        instance_of_ids = []
        for claim in claims["P31"]:
            qid = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if qid:
                instance_of_ids.append(qid)

        # Check for known types
        person_types = {"Q5"}  # Human
        place_types = {"Q515", "Q6256", "Q486972"}  # City, Country, Human settlement
        org_types = {"Q43229", "Q4830453", "Q783794"}  # Organization, Business, Company
        work_types = {"Q11424", "Q7725634", "Q571"}  # Film, Literary work, Book
        event_types = {"Q1190554", "Q1656682"}  # Occurrence, Event

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
            # Format: +1879-03-14T00:00:00Z -> 1879-03-14
            if time_str:
                return time_str[1:11]  # Skip the + and take YYYY-MM-DD
        except (IndexError, KeyError):
            pass
        return None

    def _extract_item_label(self, claims: dict, property_id: str) -> Optional[str]:
        """Extract an item label from Wikidata claims (would need additional API call)."""
        # For simplicity, just return the QID for now
        # A full implementation would fetch the label
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
        concurrency: int = 3,
    ) -> dict[str, Optional[EntityCard]]:
        """Fetch multiple entity cards with concurrency control.

        Args:
            entity_ids: List of Wikidata QIDs.
            use_cache: Whether to use cache.
            concurrency: Max concurrent requests.

        Returns:
            Dict mapping entity IDs to cards (or None).
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_limit(entity_id: str) -> tuple[str, Optional[EntityCard]]:
            async with semaphore:
                card = await self.get_entity_card(entity_id, use_cache)
                return entity_id, card

        tasks = [fetch_with_limit(eid) for eid in entity_ids]
        results = await asyncio.gather(*tasks)

        return dict(results)
