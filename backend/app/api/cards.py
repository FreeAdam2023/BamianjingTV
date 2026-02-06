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


# ============ Full-Text Entity Recognition ============

class FullTextEntityRequest(BaseModel):
    """Request body for full-text entity recognition."""
    force_refresh: bool = False
    extraction_method: str = "llm"


class FullTextEntityResponse(BaseModel):
    """Response from full-text entity recognition."""
    timeline_id: str
    segments_analyzed: int
    total_entities: int
    unique_entities: int
    message: str


@router.post("/timelines/{timeline_id}/analyze-entities", response_model=FullTextEntityResponse)
async def analyze_timeline_entities(
    timeline_id: str,
    request: FullTextEntityRequest = FullTextEntityRequest(),
):
    """Analyze entities for entire timeline using full-text context.

    This provides better disambiguation than per-segment analysis.
    Sends the complete transcript to TomTrove for entity recognition,
    then maps entities back to individual segments.

    Args:
        timeline_id: Timeline to analyze.
        force_refresh: If True, bypass cache and re-recognize entities.
        extraction_method: Entity extraction method (llm, azure, auto).
    """
    from app.models.card import SegmentAnnotations, EntityAnnotation, EntityType

    manager = _get_timeline_manager()
    timeline = manager.get_timeline(timeline_id)

    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Build full text with segment boundaries
    # Format: each segment's English text with a marker
    segment_texts = []
    segment_boundaries = []  # (start_char, end_char, segment_id)
    current_pos = 0

    for segment in timeline.segments:
        text = segment.en.strip()
        if not text:
            continue
        start = current_pos
        end = current_pos + len(text)
        segment_texts.append(text)
        segment_boundaries.append((start, end, segment.id))
        current_pos = end + 1  # +1 for separator

    full_text = " ".join(segment_texts)

    logger.info(f"Analyzing entities for timeline {timeline_id}: {len(full_text)} chars, {len(segment_boundaries)} segments")

    # Call TomTrove for full-text entity recognition
    generator = _get_card_generator()
    all_entities = []

    try:
        base_url = generator.tomtrove_url.rstrip("/")
        url = f"{base_url}/entities/recognize"

        # Include video title as context hint
        context_text = f"Video: {timeline.source_title}\n\n{full_text}"

        client = await generator._get_client()
        response = await client.post(
            url,
            json={
                "text": context_text,
                "force_refresh": request.force_refresh,
                "extraction_method": request.extraction_method,
            },
            timeout=60.0,  # Longer timeout for full text
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                raw_entities = data.get("data", {}).get("entities", [])
                # Adjust char positions for the context prefix
                prefix_len = len(f"Video: {timeline.source_title}\n\n")

                for e in raw_entities:
                    mentions = e.get("mentions", [])
                    for mention in mentions:
                        # Adjust position for prefix
                        char_start = mention.get("char_start", 0) - prefix_len
                        char_end = mention.get("char_end", 0) - prefix_len

                        if char_start < 0:
                            continue  # Skip entities in the title prefix

                        entity_type_str = e.get("entity_type", "other").lower()
                        try:
                            entity_type = EntityType(entity_type_str)
                        except ValueError:
                            entity_type = EntityType.OTHER

                        all_entities.append({
                            "text": mention.get("text", ""),
                            "entity_id": e.get("entity_id"),
                            "entity_type": entity_type,
                            "char_start": char_start,
                            "char_end": char_end,
                            "confidence": e.get("confidence", 0.0),
                        })

                logger.info(f"TomTrove recognized {len(all_entities)} entity mentions in full text")
        else:
            logger.warning(f"TomTrove full-text entity recognition failed: {response.status_code}")

    except Exception as e:
        logger.error(f"Failed to call TomTrove for full-text entity recognition: {e}")

    # Map entities back to segments
    segment_annotations = {}
    unique_entity_ids = set()

    for start, end, segment_id in segment_boundaries:
        segment_entities = []
        for entity in all_entities:
            # Check if entity overlaps with this segment
            e_start = entity["char_start"]
            e_end = entity["char_end"]
            if e_start >= start and e_end <= end:
                # Adjust position relative to segment
                segment_entities.append(EntityAnnotation(
                    text=entity["text"],
                    entity_id=entity["entity_id"],
                    entity_type=entity["entity_type"],
                    start_char=e_start - start,
                    end_char=e_end - start,
                    confidence=entity["confidence"],
                ))
                if entity["entity_id"]:
                    unique_entity_ids.add(entity["entity_id"])

        # Create annotation for this segment
        annotation = SegmentAnnotations(
            segment_id=segment_id,
            words=[],
            entities=segment_entities,
        )
        segment_annotations[segment_id] = annotation.model_dump()

    # Update timeline with all annotations
    timeline.segment_annotations = segment_annotations
    manager.save_timeline(timeline)

    logger.info(f"Analyzed entities for timeline {timeline_id}: {len(all_entities)} mentions, {len(unique_entity_ids)} unique entities")

    return FullTextEntityResponse(
        timeline_id=timeline_id,
        segments_analyzed=len(segment_boundaries),
        total_entities=len(all_entities),
        unique_entities=len(unique_entity_ids),
        message=f"Analyzed {len(segment_boundaries)} segments, found {len(unique_entity_ids)} unique entities",
    )


# ============ Manual Entity Management ============

class ManualEntityRequest(BaseModel):
    """Request body for manually adding/updating an entity."""
    segment_id: int
    text: str  # The text span in the segment
    wikipedia_url: Opt[str] = None  # Wikipedia URL to extract QID from
    entity_id: Opt[str] = None  # Or directly provide Wikidata QID
    start_char: Opt[int] = None  # Position in segment text
    end_char: Opt[int] = None


class ManualEntityResponse(BaseModel):
    """Response from manual entity operation."""
    success: bool
    entity_id: Opt[str] = None
    entity_name: Opt[str] = None
    message: str


def extract_qid_from_wikipedia_url(url: str) -> Opt[str]:
    """Extract article title from Wikipedia URL and search for QID."""
    import re
    from urllib.parse import unquote
    # Match patterns like:
    # https://en.wikipedia.org/wiki/Article_Name
    # https://zh.wikipedia.org/wiki/文章名
    # https://zh.wikipedia.org/zh-cn/文章名 (Chinese variants)
    # https://zh.wikipedia.org/zh-tw/文章名

    # Standard /wiki/ path
    match = re.search(r'wikipedia\.org/wiki/([^#?]+)', url)
    if match:
        return unquote(match.group(1).replace('_', ' '))

    # Chinese variant paths: /zh-cn/, /zh-tw/, /zh-hans/, /zh-hant/, etc.
    match = re.search(r'wikipedia\.org/zh-\w+/([^#?]+)', url)
    if match:
        return unquote(match.group(1).replace('_', ' '))

    return None


@router.post("/timelines/{timeline_id}/segments/{segment_id}/entities", response_model=ManualEntityResponse)
async def add_manual_entity(
    timeline_id: str,
    segment_id: int,
    request: ManualEntityRequest,
):
    """Manually add or update an entity annotation for a segment.

    You can provide either:
    - A Wikipedia URL (will be resolved to Wikidata QID)
    - A Wikidata QID directly (e.g., Q12345)

    Args:
        timeline_id: Timeline ID.
        segment_id: Segment ID to add entity to.
        request: Entity details including text and Wikipedia URL or QID.
    """
    from app.models.card import SegmentAnnotations, EntityAnnotation, EntityType

    manager = _get_timeline_manager()
    timeline = manager.get_timeline(timeline_id)

    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    # Find the segment
    segment = next((s for s in timeline.segments if s.id == segment_id), None)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")

    generator = _get_card_generator()
    entity_id = request.entity_id

    # If Wikipedia URL provided, resolve to QID (takes precedence over entity_id)
    if request.wikipedia_url:
        article_title = extract_qid_from_wikipedia_url(request.wikipedia_url)
        if not article_title:
            return ManualEntityResponse(
                success=False,
                message="Could not parse Wikipedia URL"
            )

        # Search for QID via Wikidata API
        try:
            client = await generator._get_client()
            # Determine language from URL
            import re
            lang_match = re.search(r'(\w+)\.wikipedia\.org', request.wikipedia_url)
            lang = lang_match.group(1) if lang_match else "en"

            # Use Wikidata's sitelinks to find QID
            response = await client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities",
                    "sites": f"{lang}wiki",
                    "titles": article_title,
                    "format": "json",
                    "props": "labels",
                },
            )

            if response.status_code == 200:
                data = response.json()
                entities = data.get("entities", {})
                for qid, entity_data in entities.items():
                    if qid.startswith("Q") and "missing" not in entity_data:
                        entity_id = qid
                        break

            if not entity_id:
                # Fallback: search by title
                entity_id = await generator.search_entity(article_title)

        except Exception as e:
            logger.error(f"Failed to resolve Wikipedia URL: {e}")
            return ManualEntityResponse(
                success=False,
                message=f"Failed to resolve Wikipedia URL: {str(e)}"
            )

    if not entity_id:
        return ManualEntityResponse(
            success=False,
            message="Could not find Wikidata entity. Please provide a valid Wikipedia URL or QID."
        )

    # Fetch entity details to get name and type
    entity_card = await generator.get_entity_card(entity_id, use_cache=True)
    entity_name = entity_card.name if entity_card else request.text
    entity_type = entity_card.entity_type if entity_card else EntityType.OTHER

    # Calculate position if not provided
    start_char = request.start_char
    end_char = request.end_char
    if start_char is None or end_char is None:
        # Try to find text in segment
        pos = segment.en.find(request.text)
        if pos >= 0:
            start_char = pos
            end_char = pos + len(request.text)
        else:
            start_char = 0
            end_char = len(request.text)

    # Create new entity annotation
    new_entity = EntityAnnotation(
        text=request.text,
        entity_id=entity_id,
        entity_type=entity_type,
        start_char=start_char,
        end_char=end_char,
        confidence=1.0,  # Manual = full confidence
    )

    # Get or create segment annotations
    if segment_id not in timeline.segment_annotations:
        timeline.segment_annotations[segment_id] = {
            "segment_id": segment_id,
            "words": [],
            "entities": [],
        }

    # Check if entity already exists (by text), update if so
    existing_entities = timeline.segment_annotations[segment_id].get("entities", [])
    updated = False
    for i, e in enumerate(existing_entities):
        if e.get("text") == request.text:
            existing_entities[i] = new_entity.model_dump()
            updated = True
            break

    if not updated:
        existing_entities.append(new_entity.model_dump())

    timeline.segment_annotations[segment_id]["entities"] = existing_entities
    manager.save_timeline(timeline)

    logger.info(f"{'Updated' if updated else 'Added'} manual entity {entity_id} ({entity_name}) to segment {segment_id}")

    return ManualEntityResponse(
        success=True,
        entity_id=entity_id,
        entity_name=entity_name,
        message=f"{'Updated' if updated else 'Added'} entity: {entity_name} ({entity_id})"
    )


@router.delete("/timelines/{timeline_id}/segments/{segment_id}/entities/{entity_text}")
async def delete_segment_entity(
    timeline_id: str,
    segment_id: int,
    entity_text: str,
):
    """Delete an entity annotation from a segment.

    Args:
        timeline_id: Timeline ID.
        segment_id: Segment ID.
        entity_text: Text of the entity to delete.
    """
    manager = _get_timeline_manager()
    timeline = manager.get_timeline(timeline_id)

    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline not found")

    if segment_id not in timeline.segment_annotations:
        raise HTTPException(status_code=404, detail="Segment has no annotations")

    entities = timeline.segment_annotations[segment_id].get("entities", [])
    original_count = len(entities)
    entities = [e for e in entities if e.get("text") != entity_text]

    if len(entities) == original_count:
        raise HTTPException(status_code=404, detail="Entity not found")

    timeline.segment_annotations[segment_id]["entities"] = entities
    manager.save_timeline(timeline)

    return {"message": f"Deleted entity: {entity_text}"}


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
