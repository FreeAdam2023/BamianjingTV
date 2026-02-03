"""Card data models for word and entity cards."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PartOfSpeech(str, Enum):
    """Part of speech categories."""
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"
    PRONOUN = "pronoun"
    PREPOSITION = "preposition"
    CONJUNCTION = "conjunction"
    INTERJECTION = "interjection"
    DETERMINER = "determiner"
    PHRASE = "phrase"
    IDIOM = "idiom"
    OTHER = "other"


class EntityType(str, Enum):
    """Entity type categories."""
    PERSON = "person"
    PLACE = "place"
    ORGANIZATION = "organization"
    EVENT = "event"
    WORK = "work"  # Movies, books, songs, etc.
    CONCEPT = "concept"
    PRODUCT = "product"
    OTHER = "other"


# ============ Word Card Models ============

class Pronunciation(BaseModel):
    """Word pronunciation data."""
    ipa: str  # IPA phonetic transcription
    audio_url: Optional[str] = None  # URL to audio file
    region: str = "us"  # us, uk, au, etc.


class WordSense(BaseModel):
    """A single meaning/sense of a word."""
    part_of_speech: str
    definition: str
    definition_zh: Optional[str] = None  # Chinese translation of definition
    examples: List[str] = Field(default_factory=list)
    examples_zh: List[str] = Field(default_factory=list)  # Chinese translations
    synonyms: List[str] = Field(default_factory=list)
    antonyms: List[str] = Field(default_factory=list)


class WordCard(BaseModel):
    """Word card with dictionary data."""
    word: str
    lemma: str  # Base/root form
    pronunciations: List[Pronunciation] = Field(default_factory=list)
    senses: List[WordSense] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)  # Image URLs
    frequency_rank: Optional[int] = None  # Word frequency rank (lower = more common)
    cefr_level: Optional[str] = None  # A1, A2, B1, B2, C1, C2

    # Metadata
    source: str = "free_dictionary"  # API source
    fetched_at: datetime = Field(default_factory=datetime.now)

    @property
    def primary_pronunciation(self) -> Optional[Pronunciation]:
        """Get the primary (US) pronunciation."""
        for p in self.pronunciations:
            if p.region == "us":
                return p
        return self.pronunciations[0] if self.pronunciations else None


# ============ Entity Card Models ============

class EntityLocalization(BaseModel):
    """Localized entity data for a specific language."""
    name: str
    description: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)


class EntityCard(BaseModel):
    """Entity card with Wikipedia/Wikidata data."""
    entity_id: str  # Wikidata QID (e.g., Q42)
    entity_type: EntityType
    name: str  # Primary name (English)
    description: str  # Short description

    # Links
    wikipedia_url: Optional[str] = None
    wikidata_url: Optional[str] = None
    official_website: Optional[str] = None

    # Media
    image_url: Optional[str] = None

    # Type-specific fields
    birth_date: Optional[str] = None  # For persons
    death_date: Optional[str] = None  # For persons
    nationality: Optional[str] = None  # For persons
    location: Optional[str] = None  # For places
    coordinates: Optional[Dict[str, float]] = None  # lat, lon for places
    founded_date: Optional[str] = None  # For organizations

    # Localizations
    localizations: Dict[str, EntityLocalization] = Field(default_factory=dict)

    # Metadata
    source: str = "wikidata"
    fetched_at: datetime = Field(default_factory=datetime.now)

    def get_localized(self, lang: str = "zh") -> EntityLocalization:
        """Get localized data for a language."""
        if lang in self.localizations:
            return self.localizations[lang]
        # Fallback to English
        return EntityLocalization(name=self.name, description=self.description)


# ============ NER Annotation Models ============

class WordAnnotation(BaseModel):
    """A word annotation within a segment."""
    word: str
    lemma: str
    start_char: int  # Character offset in segment text
    end_char: int
    is_vocabulary: bool = False  # Is this a vocabulary word to learn?
    difficulty_level: Optional[str] = None  # easy, medium, hard


class EntityAnnotation(BaseModel):
    """An entity annotation within a segment."""
    text: str  # Surface form in text
    entity_id: Optional[str] = None  # Wikidata QID if resolved
    entity_type: EntityType
    start_char: int
    end_char: int
    confidence: float = 1.0


class SegmentAnnotations(BaseModel):
    """NER annotations for a single segment."""
    segment_id: int
    words: List[WordAnnotation] = Field(default_factory=list)
    entities: List[EntityAnnotation] = Field(default_factory=list)


class TimelineAnnotations(BaseModel):
    """All NER annotations for a timeline."""
    timeline_id: str
    segments: List[SegmentAnnotations] = Field(default_factory=list)

    # Aggregated unique items
    unique_words: List[str] = Field(default_factory=list)
    unique_entities: List[str] = Field(default_factory=list)

    # Processing metadata
    processed_at: datetime = Field(default_factory=datetime.now)
    model_used: str = "spacy"


# ============ API Request/Response Models ============

class CardGenerateRequest(BaseModel):
    """Request to generate cards for a timeline."""
    word_limit: int = 50  # Max vocabulary words to extract
    entity_limit: int = 20  # Max entities to extract
    min_word_frequency: int = 1  # Min occurrences to include
    difficulty_filter: Optional[str] = None  # Filter by difficulty


class CardGenerateResponse(BaseModel):
    """Response from card generation."""
    timeline_id: str
    words_extracted: int
    entities_extracted: int
    cards_generated: int
    message: str


class WordCardResponse(BaseModel):
    """API response for a word card."""
    word: str
    found: bool
    card: Optional[WordCard] = None
    error: Optional[str] = None


class EntityCardResponse(BaseModel):
    """API response for an entity card."""
    entity_id: str
    found: bool
    card: Optional[EntityCard] = None
    error: Optional[str] = None
