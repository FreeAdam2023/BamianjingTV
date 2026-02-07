"""Card cache service for storing and retrieving word/entity cards."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from loguru import logger

from app.config import settings
from app.models.card import WordCard, EntityCard, IdiomCard


class CardCache:
    """Cache for word and entity cards.

    Cards are stored as JSON files on disk:
    - data/cards/words/{word}.json
    - data/cards/entities/{entity_id}.json

    Cache entries expire after a configurable TTL (default 30 days).
    """

    def __init__(
        self,
        cards_dir: Optional[Path] = None,
        ttl_days: int = 30,
    ):
        """Initialize card cache.

        Args:
            cards_dir: Directory for card storage. Defaults to data/cards.
            ttl_days: Cache TTL in days.
        """
        self.cards_dir = cards_dir or settings.data_dir / "cards"
        self.words_dir = self.cards_dir / "words"
        self.entities_dir = self.cards_dir / "entities"
        self.idioms_dir = self.cards_dir / "idioms"
        self.ttl = timedelta(days=ttl_days)

        # Create directories
        self.words_dir.mkdir(parents=True, exist_ok=True)
        self.entities_dir.mkdir(parents=True, exist_ok=True)
        self.idioms_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"CardCache initialized at {self.cards_dir}")

    def _is_expired(self, fetched_at: datetime) -> bool:
        """Check if a cached entry has expired."""
        return datetime.now() - fetched_at > self.ttl

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string for use as a filename."""
        # Replace problematic characters
        sanitized = name.lower().replace(" ", "_").replace("/", "_").replace("\\", "_")
        # Remove any remaining non-alphanumeric characters except underscore and hyphen
        return "".join(c for c in sanitized if c.isalnum() or c in "_-")

    # ============ Word Cards ============

    def get_word_card(self, word: str, cache_key: Optional[str] = None) -> Optional[WordCard]:
        """Get a word card from cache.

        Args:
            word: The word to look up.
            cache_key: Optional custom cache key (e.g., "word:zh-TW" for translated cards).

        Returns:
            WordCard if found and not expired, None otherwise.
        """
        key = cache_key or word
        filename = self._sanitize_filename(key) + ".json"
        file_path = self.words_dir / filename

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            card = WordCard.model_validate(data)

            # Check expiration
            if self._is_expired(card.fetched_at):
                logger.debug(f"Word card expired: {word}")
                return None

            logger.debug(f"Word card cache hit: {word}")
            return card

        except Exception as e:
            logger.warning(f"Failed to load word card {word}: {e}")
            return None

    def set_word_card(self, card: WordCard, cache_key: Optional[str] = None) -> None:
        """Store a word card in cache.

        Args:
            card: WordCard to store.
            cache_key: Optional custom cache key (e.g., "word:zh-TW" for translated cards).
        """
        key = cache_key or card.word
        filename = self._sanitize_filename(key) + ".json"
        file_path = self.words_dir / filename

        try:
            # Update fetch time
            card.fetched_at = datetime.now()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(card.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

            logger.debug(f"Word card cached: {card.word}")

        except Exception as e:
            logger.error(f"Failed to cache word card {card.word}: {e}")

    def delete_word_card(self, word: str) -> bool:
        """Delete a word card from cache.

        Args:
            word: The word to delete.

        Returns:
            True if deleted, False if not found.
        """
        filename = self._sanitize_filename(word) + ".json"
        file_path = self.words_dir / filename

        if file_path.exists():
            file_path.unlink()
            logger.debug(f"Word card deleted: {word}")
            return True
        return False

    # ============ Entity Cards ============

    def get_entity_card(self, entity_id: str) -> Optional[EntityCard]:
        """Get an entity card from cache.

        Args:
            entity_id: Wikidata QID (e.g., Q42).

        Returns:
            EntityCard if found and not expired, None otherwise.
        """
        filename = self._sanitize_filename(entity_id) + ".json"
        file_path = self.entities_dir / filename

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            card = EntityCard.model_validate(data)

            # Check expiration
            if self._is_expired(card.fetched_at):
                logger.debug(f"Entity card expired: {entity_id}")
                return None

            logger.debug(f"Entity card cache hit: {entity_id}")
            return card

        except Exception as e:
            logger.warning(f"Failed to load entity card {entity_id}: {e}")
            return None

    def set_entity_card(self, card: EntityCard) -> None:
        """Store an entity card in cache.

        Args:
            card: EntityCard to store.
        """
        filename = self._sanitize_filename(card.entity_id) + ".json"
        file_path = self.entities_dir / filename

        try:
            # Update fetch time
            card.fetched_at = datetime.now()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(card.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

            logger.debug(f"Entity card cached: {card.entity_id}")

        except Exception as e:
            logger.error(f"Failed to cache entity card {card.entity_id}: {e}")

    def delete_entity_card(self, entity_id: str) -> bool:
        """Delete an entity card from cache.

        Args:
            entity_id: Wikidata QID to delete.

        Returns:
            True if deleted, False if not found.
        """
        filename = self._sanitize_filename(entity_id) + ".json"
        file_path = self.entities_dir / filename

        if file_path.exists():
            file_path.unlink()
            logger.debug(f"Entity card deleted: {entity_id}")
            return True
        return False

    # ============ Idiom Cards ============

    def get_idiom_card(self, idiom_text: str) -> Optional[IdiomCard]:
        """Get an idiom card from cache.

        Args:
            idiom_text: The idiom text to look up.

        Returns:
            IdiomCard if found and not expired, None otherwise.
        """
        filename = self._sanitize_filename(idiom_text) + ".json"
        file_path = self.idioms_dir / filename

        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            card = IdiomCard.model_validate(data)

            # Check expiration
            if self._is_expired(card.fetched_at):
                logger.debug(f"Idiom card expired: {idiom_text}")
                return None

            logger.debug(f"Idiom card cache hit: {idiom_text}")
            return card

        except Exception as e:
            logger.warning(f"Failed to load idiom card {idiom_text}: {e}")
            return None

    def set_idiom_card(self, card: IdiomCard) -> None:
        """Store an idiom card in cache.

        Args:
            card: IdiomCard to store.
        """
        filename = self._sanitize_filename(card.text) + ".json"
        file_path = self.idioms_dir / filename

        try:
            # Update fetch time
            card.fetched_at = datetime.now()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(card.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

            logger.debug(f"Idiom card cached: {card.text}")

        except Exception as e:
            logger.error(f"Failed to cache idiom card {card.text}: {e}")

    def delete_idiom_card(self, idiom_text: str) -> bool:
        """Delete an idiom card from cache.

        Args:
            idiom_text: The idiom text to delete.

        Returns:
            True if deleted, False if not found.
        """
        filename = self._sanitize_filename(idiom_text) + ".json"
        file_path = self.idioms_dir / filename

        if file_path.exists():
            file_path.unlink()
            logger.debug(f"Idiom card deleted: {idiom_text}")
            return True
        return False

    # ============ Utilities ============

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache statistics.
        """
        word_count = len(list(self.words_dir.glob("*.json")))
        entity_count = len(list(self.entities_dir.glob("*.json")))
        idiom_count = len(list(self.idioms_dir.glob("*.json")))

        return {
            "words_cached": word_count,
            "entities_cached": entity_count,
            "idioms_cached": idiom_count,
            "total_cached": word_count + entity_count + idiom_count,
            "cache_dir": str(self.cards_dir),
        }

    def clear_expired(self) -> dict:
        """Clear all expired cache entries.

        Returns:
            Dict with counts of cleared entries.
        """
        words_cleared = 0
        entities_cleared = 0

        # Clear expired word cards
        for file_path in self.words_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                fetched_at = datetime.fromisoformat(data.get("fetched_at", "2000-01-01"))
                if self._is_expired(fetched_at):
                    file_path.unlink()
                    words_cleared += 1
            except Exception:
                pass

        # Clear expired entity cards
        for file_path in self.entities_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                fetched_at = datetime.fromisoformat(data.get("fetched_at", "2000-01-01"))
                if self._is_expired(fetched_at):
                    file_path.unlink()
                    entities_cleared += 1
            except Exception:
                pass

        # Clear expired idiom cards
        idioms_cleared = 0
        for file_path in self.idioms_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                fetched_at = datetime.fromisoformat(data.get("fetched_at", "2000-01-01"))
                if self._is_expired(fetched_at):
                    file_path.unlink()
                    idioms_cleared += 1
            except Exception:
                pass

        logger.info(f"Cleared {words_cleared} word cards, {entities_cleared} entity cards, {idioms_cleared} idiom cards")

        return {
            "words_cleared": words_cleared,
            "entities_cleared": entities_cleared,
            "idioms_cleared": idioms_cleared,
        }
