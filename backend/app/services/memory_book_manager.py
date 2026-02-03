"""Memory Book Manager - CRUD operations for memory books with JSON persistence."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from app.config import get_config
from app.models.memory_book import (
    MemoryBook,
    MemoryBookCreate,
    MemoryBookSummary,
    MemoryItem,
    MemoryItemCreate,
)

logger = logging.getLogger(__name__)


class MemoryBookManager:
    """Manages memory books with JSON file persistence."""

    def __init__(self):
        self._config = get_config()
        self._books: Dict[str, MemoryBook] = {}
        self._storage_dir = self._config.data_dir / "memory_books"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load_all()

    def _load_all(self) -> None:
        """Load all memory books from disk."""
        count = 0
        for path in self._storage_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                book = MemoryBook(**data)
                self._books[book.book_id] = book
                count += 1
            except Exception as e:
                logger.error(f"Failed to load memory book from {path}: {e}")
        logger.info(f"Loaded {count} memory books")

    def _save_book(self, book: MemoryBook) -> None:
        """Save a memory book to disk."""
        path = self._storage_dir / f"{book.book_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(book.model_dump(mode="json"), f, indent=2, default=str)

    def _delete_book_file(self, book_id: str) -> None:
        """Delete a memory book file from disk."""
        path = self._storage_dir / f"{book_id}.json"
        if path.exists():
            path.unlink()

    # --- Memory Book CRUD ---

    def create_book(self, data: MemoryBookCreate) -> MemoryBook:
        """Create a new memory book."""
        book = MemoryBook(
            name=data.name,
            description=data.description,
        )
        self._books[book.book_id] = book
        self._save_book(book)
        logger.info(f"Created memory book: {book.book_id} - {book.name}")
        return book

    def get_book(self, book_id: str) -> Optional[MemoryBook]:
        """Get a memory book by ID."""
        return self._books.get(book_id)

    def list_books(self) -> List[MemoryBookSummary]:
        """List all memory books (summary only)."""
        return [
            MemoryBookSummary.from_book(book)
            for book in sorted(
                self._books.values(),
                key=lambda b: b.updated_at,
                reverse=True,
            )
        ]

    def update_book(
        self, book_id: str, name: Optional[str] = None, description: Optional[str] = None
    ) -> Optional[MemoryBook]:
        """Update a memory book's metadata."""
        book = self._books.get(book_id)
        if not book:
            return None
        if name is not None:
            book.name = name
        if description is not None:
            book.description = description
        book.updated_at = datetime.now()
        self._save_book(book)
        return book

    def delete_book(self, book_id: str) -> bool:
        """Delete a memory book."""
        if book_id not in self._books:
            return False
        del self._books[book_id]
        self._delete_book_file(book_id)
        logger.info(f"Deleted memory book: {book_id}")
        return True

    # --- Memory Item CRUD ---

    def add_item(self, book_id: str, data: MemoryItemCreate) -> Optional[MemoryItem]:
        """Add an item to a memory book."""
        book = self._books.get(book_id)
        if not book:
            return None

        item = MemoryItem(
            book_id=book_id,
            target_type=data.target_type,
            target_id=data.target_id,
            source_timeline_id=data.source_timeline_id,
            source_timecode=data.source_timecode,
            source_segment_text=data.source_segment_text,
            user_notes=data.user_notes,
            tags=data.tags,
            card_data=data.card_data,
        )
        book.add_item(item)
        self._save_book(book)
        logger.info(f"Added item {item.item_id} to book {book_id}")
        return item

    def get_items(self, book_id: str) -> Optional[List[MemoryItem]]:
        """Get all items in a memory book."""
        book = self._books.get(book_id)
        if not book:
            return None
        return book.items

    def get_item(self, book_id: str, item_id: str) -> Optional[MemoryItem]:
        """Get a specific item from a memory book."""
        book = self._books.get(book_id)
        if not book:
            return None
        return book.get_item(item_id)

    def update_item(
        self,
        book_id: str,
        item_id: str,
        user_notes: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Optional[MemoryItem]:
        """Update an item in a memory book."""
        book = self._books.get(book_id)
        if not book:
            return None
        item = book.get_item(item_id)
        if not item:
            return None
        if user_notes is not None:
            item.user_notes = user_notes
        if tags is not None:
            item.tags = tags
        book.updated_at = datetime.now()
        self._save_book(book)
        return item

    def remove_item(self, book_id: str, item_id: str) -> bool:
        """Remove an item from a memory book."""
        book = self._books.get(book_id)
        if not book:
            return False
        if book.remove_item(item_id):
            self._save_book(book)
            logger.info(f"Removed item {item_id} from book {book_id}")
            return True
        return False

    # --- Utility Methods ---

    def get_default_book(self) -> MemoryBook:
        """Get or create the default memory book."""
        default_name = "My Collection"
        for book in self._books.values():
            if book.name == default_name:
                return book
        # Create default book
        return self.create_book(MemoryBookCreate(
            name=default_name,
            description="Default collection for words and entities",
        ))

    def find_item_by_target(
        self, book_id: str, target_type: str, target_id: str
    ) -> Optional[MemoryItem]:
        """Find an item by its target (to check if already collected)."""
        book = self._books.get(book_id)
        if not book:
            return None
        for item in book.items:
            if item.target_type == target_type and item.target_id == target_id:
                return item
        return None
