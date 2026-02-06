"""Cards API routes for word and entity cards."""

from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from loguru import logger

from app.models.card import (
    WordCard,
    EntityCard,
    CardGenerateRequest,
    CardGenerateResponse,
    WordCardResponse,
    EntityCardResponse,
    TimelineAnnotations,
)
from app.services.card_cache import CardCache
from app.services.timeline_manager import TimelineManager
from app.workers.card_generator import CardGeneratorWorker
from app.workers.ner import NERWorker

router = APIRouter(prefix="/cards", tags=["cards"])

# Module-level instances (set at startup)
_card_cache: Optional[CardCache] = None
_card_generator: Optional[CardGeneratorWorker] = None
_ner_worker: Optional[NERWorker] = None
_timeline_manager: Optional[TimelineManager] = None


def set_card_cache(cache: CardCache) -> None:
    """Set the card cache instance."""
    global _card_cache
    _card_cache = cache


def set_card_generator(generator: CardGeneratorWorker) -> None:
    """Set the card generator worker instance."""
    global _card_generator
    _card_generator = generator


def set_ner_worker(worker: NERWorker) -> None:
    """Set the NER worker instance."""
    global _ner_worker
    _ner_worker = worker


def set_timeline_manager(manager: TimelineManager) -> None:
    """Set the timeline manager instance."""
    global _timeline_manager
    _timeline_manager = manager


def _get_card_cache() -> CardCache:
    """Get the card cache instance."""
    if _card_cache is None:
        raise RuntimeError("CardCache not initialized")
    return _card_cache


def _get_card_generator() -> CardGeneratorWorker:
    """Get the card generator instance."""
    if _card_generator is None:
        raise RuntimeError("CardGeneratorWorker not initialized")
    return _card_generator


def _get_ner_worker() -> NERWorker:
    """Get the NER worker instance."""
    if _ner_worker is None:
        raise RuntimeError("NERWorker not initialized")
    return _ner_worker


def _get_timeline_manager() -> TimelineManager:
    """Get the timeline manager instance."""
    if _timeline_manager is None:
        raise RuntimeError("TimelineManager not initialized")
    return _timeline_manager


# ============ Word Card Endpoints ============

@router.get("/words/{word}", response_model=WordCardResponse)
async def get_word_card(
    word: str,
    lang: Optional[str] = None,
    force_refresh: bool = False,
):
    """Get a word card by word.

    Fetches from cache first, then from dictionary API if not cached.

    Args:
        word: The word to look up.
        lang: Target language for translations (zh-TW for Traditional Chinese,
              zh-CN for Simplified Chinese). If None, returns English only.
        force_refresh: If True, bypass cache and fetch fresh data.
    """
    generator = _get_card_generator()

    try:
        card = await generator.get_word_card(
            word,
            use_cache=not force_refresh,
            target_lang=lang,
        )

        if card:
            return WordCardResponse(word=word, found=True, card=card)
        else:
            return WordCardResponse(word=word, found=False, error="Word not found in dictionary")

    except Exception as e:
        logger.error(f"Error fetching word card for {word}: {e}")
        return WordCardResponse(word=word, found=False, error=str(e))


@router.delete("/words/{word}")
async def delete_word_card(word: str):
    """Delete a word card from cache."""
    cache = _get_card_cache()

    if cache.delete_word_card(word):
        return {"message": f"Word card '{word}' deleted from cache"}
    else:
        raise HTTPException(status_code=404, detail="Word card not found in cache")


# ============ Entity Card Endpoints ============

@router.get("/entities/details", response_model=EntityCardResponse)
async def get_entity_details(
    entity_id: str,
    force_refresh: bool = False,
):
    """Get entity details by Wikidata QID.

    Step 2: Called when user clicks on an entity tag.
    Uses TomTrove /entities/details?entity_id=... internally.

    Args:
        entity_id: Wikidata QID (e.g., Q235328)
        force_refresh: If True, bypass cache and fetch fresh data.
    """
    generator = _get_card_generator()

    try:
        card = await generator.get_entity_card(
            entity_id,
            use_cache=not force_refresh,
        )

        if card:
            return EntityCardResponse(entity_id=entity_id, found=True, card=card)
        else:
            return EntityCardResponse(entity_id=entity_id, found=False, error="Entity not found")

    except Exception as e:
        logger.error(f"Error fetching entity card for {entity_id}: {e}")
        return EntityCardResponse(entity_id=entity_id, found=False, error=str(e))


# Keep old endpoint for backwards compatibility
@router.get("/entities/{entity_id}", response_model=EntityCardResponse)
async def get_entity_card(entity_id: str, force_refresh: bool = False):
    """Get an entity card by Wikidata QID (legacy path parameter version)."""
    return await get_entity_details(entity_id, force_refresh)


from pydantic import BaseModel
from typing import List, Optional as Opt

class EntityRecognizeRequest(BaseModel):
    """Request body for entity recognition."""
    text: str
    force_refresh: bool = True
    extraction_method: str = "llm"

class RecognizedEntity(BaseModel):
    """A recognized entity."""
    entity_id: str
    entity_type: str
    text: str
    confidence: float

class EntityRecognizeResponse(BaseModel):
    """Response from entity recognition."""
    success: bool
    entities: List[RecognizedEntity]
    message: Opt[str] = None

@router.post("/entities/recognize", response_model=EntityRecognizeResponse)
async def recognize_entities(request: EntityRecognizeRequest):
    """Recognize entities in text.

    Step 1: Called when user clicks on a subtitle line.
    Uses TomTrove /entities/recognize internally.

    Returns list of entities with their QIDs and types.
    """
    generator = _get_card_generator()

    try:
        # Call TomTrove entity recognition
        import httpx

        base_url = generator.tomtrove_url.rstrip("/")
        url = f"{base_url}/entities/recognize"

        client = await generator._get_client()
        response = await client.post(
            url,
            json={
                "text": request.text,
                "force_refresh": request.force_refresh,
                "extraction_method": request.extraction_method,
            },
        )

        if response.status_code != 200:
            logger.warning(f"TomTrove entity recognition failed: {response.status_code}")
            return EntityRecognizeResponse(
                success=False,
                entities=[],
                message=f"Recognition failed: {response.status_code}"
            )

        data = response.json()

        if not data.get("success"):
            return EntityRecognizeResponse(
                success=False,
                entities=[],
                message=data.get("message", "Recognition unsuccessful")
            )

        # Parse entities from response
        raw_entities = data.get("data", {}).get("entities", [])
        entities = []

        for e in raw_entities:
            # Get the first mention text
            mentions = e.get("mentions", [])
            text = mentions[0].get("text", "") if mentions else ""

            entities.append(RecognizedEntity(
                entity_id=e.get("entity_id", ""),
                entity_type=e.get("entity_type", "Unknown"),
                text=text,
                confidence=e.get("confidence", 0.0),
            ))

        logger.info(f"Recognized {len(entities)} entities in text")

        return EntityRecognizeResponse(
            success=True,
            entities=entities,
            message=f"Found {len(entities)} entities"
        )

    except Exception as e:
        logger.error(f"Error recognizing entities: {e}")
        return EntityRecognizeResponse(
            success=False,
            entities=[],
            message=str(e)
        )


@router.delete("/entities/{entity_id}")
async def delete_entity_card(entity_id: str):
    """Delete an entity card from cache."""
    cache = _get_card_cache()

    if cache.delete_entity_card(entity_id):
        return {"message": f"Entity card '{entity_id}' deleted from cache"}
    else:
        raise HTTPException(status_code=404, detail="Entity card not found in cache")


# ============ Timeline Card Generation ============

@router.post("/timelines/{timeline_id}/generate", response_model=CardGenerateResponse)
async def generate_cards_for_timeline(
    timeline_id: str,
    request: CardGenerateRequest = CardGenerateRequest(),
    background_tasks: BackgroundTasks = None,
):
    """Generate word and entity cards for a timeline.

    This extracts vocabulary and entities from the timeline's English text
    and fetches card data from external APIs.
    """
    manager = _get_timeline_manager()
    timeline = manager.get_timeline(timeline_id)

    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    ner_worker = _get_ner_worker()
    generator = _get_card_generator()

    # Extract vocabulary and entities
    annotations = ner_worker.process_timeline(
        timeline,
        extract_vocabulary=True,
        extract_entities=True,
        vocabulary_limit=request.word_limit,
        entity_limit=request.entity_limit,
    )

    # Fetch cards in background for better response time
    words_to_fetch = annotations.unique_words
    entities_to_search = annotations.unique_entities

    cards_generated = 0

    # Fetch word cards
    if words_to_fetch:
        word_cards = await generator.get_word_cards_batch(words_to_fetch)
        cards_generated += sum(1 for c in word_cards.values() if c is not None)

    # Search and fetch entity cards
    if entities_to_search:
        for entity_text in entities_to_search[:request.entity_limit]:
            # Try to find Wikidata QID
            qid = await generator.search_entity(entity_text)
            if qid:
                card = await generator.get_entity_card(qid)
                if card:
                    cards_generated += 1

    logger.info(
        f"Generated cards for timeline {timeline_id}: "
        f"{len(words_to_fetch)} words, {len(entities_to_search)} entities, "
        f"{cards_generated} cards fetched"
    )

    return CardGenerateResponse(
        timeline_id=timeline_id,
        words_extracted=len(words_to_fetch),
        entities_extracted=len(entities_to_search),
        cards_generated=cards_generated,
        message=f"Extracted {len(words_to_fetch)} vocabulary words and {len(entities_to_search)} entities",
    )


@router.get("/timelines/{timeline_id}/annotations", response_model=TimelineAnnotations)
async def get_timeline_annotations(
    timeline_id: str,
    vocabulary_limit: int = 50,
    entity_limit: int = 20,
):
    """Get NER annotations for a timeline.

    Returns vocabulary words and entities extracted from the timeline.
    """
    manager = _get_timeline_manager()
    timeline = manager.get_timeline(timeline_id)

    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    ner_worker = _get_ner_worker()

    annotations = ner_worker.process_timeline(
        timeline,
        extract_vocabulary=True,
        extract_entities=True,
        vocabulary_limit=vocabulary_limit,
        entity_limit=entity_limit,
    )

    return annotations


class SegmentAnnotationRequest(BaseModel):
    """Request body for segment annotation."""
    text: str
    force_refresh: bool = False
    extraction_method: str = "llm"
    # Optional: for caching in timeline
    timeline_id: Opt[str] = None
    segment_id: Opt[int] = None


@router.post("/segments/annotations")
async def get_segment_annotations(request: SegmentAnnotationRequest):
    """Get NER annotations for text.

    Uses TomTrove /entities/recognize for entity recognition.
    Optionally caches results in timeline if timeline_id and segment_id provided.

    Args:
        text: The text to analyze.
        force_refresh: If True, bypass cache and re-recognize entities.
        extraction_method: Entity extraction method (llm, azure, auto).
        timeline_id: Optional timeline ID for caching.
        segment_id: Optional segment ID for caching.
    """
    from app.models.card import SegmentAnnotations, EntityAnnotation, EntityType

    # Check cache if timeline_id and segment_id provided
    manager = None
    timeline = None
    if request.timeline_id and request.segment_id is not None:
        manager = _get_timeline_manager()
        timeline = manager.get_timeline(request.timeline_id)

        if timeline and not request.force_refresh and request.segment_id in timeline.segment_annotations:
            logger.info(f"Using cached annotations for segment {request.segment_id}")
            cached = timeline.segment_annotations[request.segment_id]
            return SegmentAnnotations(**cached)

    # Use TomTrove for entity recognition
    generator = _get_card_generator()
    entities = []

    try:
        base_url = generator.tomtrove_url.rstrip("/")
        url = f"{base_url}/entities/recognize"

        client = await generator._get_client()
        response = await client.post(
            url,
            json={
                "text": request.text,
                "force_refresh": request.force_refresh,
                "extraction_method": request.extraction_method,
            },
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                raw_entities = data.get("data", {}).get("entities", [])
                for e in raw_entities:
                    mentions = e.get("mentions", [])
                    if mentions:
                        mention = mentions[0]
                        entity_type_str = e.get("entity_type", "other").lower()
                        try:
                            entity_type = EntityType(entity_type_str)
                        except ValueError:
                            entity_type = EntityType.OTHER

                        entities.append(EntityAnnotation(
                            text=mention.get("text", ""),
                            entity_id=e.get("entity_id"),
                            entity_type=entity_type,
                            start_char=mention.get("char_start", 0),
                            end_char=mention.get("char_end", 0),
                            confidence=e.get("confidence", 0.0),
                        ))
                logger.info(f"TomTrove recognized {len(entities)} entities")
        else:
            logger.warning(f"TomTrove entity recognition failed: {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to call TomTrove entity recognition: {e}")

    # Create annotation with entities only (skip vocabulary extraction)
    annotation = SegmentAnnotations(
        segment_id=request.segment_id or 0,
        words=[],  # Skip vocabulary - users click words directly for lookup
        entities=entities,
    )

    # Cache if timeline provided
    if timeline and manager and request.segment_id is not None:
        timeline.segment_annotations[request.segment_id] = annotation.model_dump()
        manager.save_timeline(timeline)
        logger.info(f"Cached annotations for segment {request.segment_id}")

    return annotation


# ============ Cache Management ============

@router.get("/cache/stats")
async def get_cache_stats():
    """Get card cache statistics."""
    cache = _get_card_cache()
    return cache.get_stats()


@router.post("/cache/clear-expired")
async def clear_expired_cache():
    """Clear expired cache entries."""
    cache = _get_card_cache()
    result = cache.clear_expired()
    return {
        "message": "Expired cache entries cleared",
        **result,
    }
