"""Memory Book models for storing user's collected words, entities, and observations."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
import uuid


class MemoryItemType(str, Enum):
    """Type of memory item."""
    WORD = "word"
    ENTITY = "entity"
    OBSERVATION = "observation"


class MemoryItem(BaseModel):
    """A single item in the memory book."""
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    book_id: str
    target_type: MemoryItemType
    target_id: str  # word string / entity QID / observation ID

    # Source information
    source_timeline_id: Optional[str] = None
    source_timecode: Optional[float] = None
    source_segment_text: Optional[str] = None  # Original sentence context

    # User additions
    user_notes: str = ""
    tags: List[str] = Field(default_factory=list)

    # Card data snapshot (for offline use)
    card_data: Optional[dict] = None  # WordCard or EntityCard data

    created_at: datetime = Field(default_factory=datetime.now)

    def to_anki_fields(self) -> dict:
        """Convert to fields for Anki card generation."""
        if self.target_type == MemoryItemType.WORD and self.card_data:
            return {
                "word": self.card_data.get("word", self.target_id),
                "lemma": self.card_data.get("lemma", ""),
                "pronunciation": self._get_pronunciation(),
                "definition": self._get_definition(),
                "examples": self._get_examples(),
                "context": self.source_segment_text or "",
                "notes": self.user_notes,
            }
        elif self.target_type == MemoryItemType.ENTITY and self.card_data:
            return {
                "name": self.card_data.get("name", self.target_id),
                "type": self.card_data.get("entity_type", ""),
                "description": self.card_data.get("description", ""),
                "wikipedia_url": self.card_data.get("wikipedia_url", ""),
                "context": self.source_segment_text or "",
                "notes": self.user_notes,
            }
        else:
            return {
                "target": self.target_id,
                "type": self.target_type.value,
                "notes": self.user_notes,
            }

    def _get_pronunciation(self) -> str:
        """Extract pronunciation from card data."""
        if not self.card_data:
            return ""
        pronunciations = self.card_data.get("pronunciations", [])
        if pronunciations:
            return pronunciations[0].get("ipa", "")
        return ""

    def _get_definition(self) -> str:
        """Extract primary definition from card data."""
        if not self.card_data:
            return ""
        senses = self.card_data.get("senses", [])
        if senses:
            return senses[0].get("definition", "")
        return ""

    def _get_examples(self) -> str:
        """Extract examples from card data."""
        if not self.card_data:
            return ""
        senses = self.card_data.get("senses", [])
        examples = []
        for sense in senses[:2]:  # First 2 senses
            examples.extend(sense.get("examples", [])[:2])  # First 2 examples each
        return "<br>".join(examples[:3])  # Max 3 examples


class MemoryBook(BaseModel):
    """A collection of memory items."""
    book_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str
    description: str = ""
    item_count: int = 0
    items: List[MemoryItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_item(self, item: MemoryItem) -> None:
        """Add an item to the book."""
        item.book_id = self.book_id
        self.items.append(item)
        self.item_count = len(self.items)
        self.updated_at = datetime.now()

    def remove_item(self, item_id: str) -> bool:
        """Remove an item from the book."""
        for i, item in enumerate(self.items):
            if item.item_id == item_id:
                self.items.pop(i)
                self.item_count = len(self.items)
                self.updated_at = datetime.now()
                return True
        return False

    def get_item(self, item_id: str) -> Optional[MemoryItem]:
        """Get an item by ID."""
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None


class MemoryBookSummary(BaseModel):
    """Summary of a memory book for list views."""
    book_id: str
    name: str
    description: str = ""
    item_count: int = 0
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_book(cls, book: MemoryBook) -> "MemoryBookSummary":
        return cls(
            book_id=book.book_id,
            name=book.name,
            description=book.description,
            item_count=book.item_count,
            created_at=book.created_at,
            updated_at=book.updated_at,
        )


# Request/Response models

class MemoryBookCreate(BaseModel):
    """Request to create a new memory book."""
    name: str
    description: str = ""


class MemoryBookUpdate(BaseModel):
    """Request to update a memory book."""
    name: Optional[str] = None
    description: Optional[str] = None


class MemoryItemCreate(BaseModel):
    """Request to add an item to a memory book."""
    target_type: MemoryItemType
    target_id: str
    source_timeline_id: Optional[str] = None
    source_timecode: Optional[float] = None
    source_segment_text: Optional[str] = None
    user_notes: str = ""
    tags: List[str] = Field(default_factory=list)
    card_data: Optional[dict] = None


class MemoryItemUpdate(BaseModel):
    """Request to update a memory item."""
    user_notes: Optional[str] = None
    tags: Optional[List[str]] = None
