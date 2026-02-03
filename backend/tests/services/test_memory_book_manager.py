"""Tests for MemoryBookManager service."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.models.memory_book import (
    MemoryBookCreate,
    MemoryItemCreate,
    MemoryItemType,
)
from app.services.memory_book_manager import MemoryBookManager


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config(temp_data_dir):
    """Create a mock config with temp directory."""
    config = MagicMock()
    config.data_dir = temp_data_dir
    return config


@pytest.fixture
def memory_book_manager(mock_config):
    """Create a memory book manager with mocked config."""
    with patch("app.services.memory_book_manager.get_config", return_value=mock_config):
        manager = MemoryBookManager()
        yield manager


class TestMemoryBookCreate:
    """Tests for creating memory books."""

    def test_create_book(self, memory_book_manager):
        """Test creating a new memory book."""
        create_data = MemoryBookCreate(
            name="Vocabulary",
            description="Words to learn",
        )

        book = memory_book_manager.create_book(create_data)

        assert book is not None
        assert book.name == "Vocabulary"
        assert book.description == "Words to learn"
        assert len(book.items) == 0

    def test_create_book_generates_id(self, memory_book_manager):
        """Test that book ID is auto-generated."""
        create_data = MemoryBookCreate(name="Test Book")

        book = memory_book_manager.create_book(create_data)

        assert book.book_id is not None
        assert len(book.book_id) > 0

    def test_create_book_persists(self, memory_book_manager, temp_data_dir):
        """Test that created book is saved to disk."""
        create_data = MemoryBookCreate(name="Test Book")
        book = memory_book_manager.create_book(create_data)

        file_path = temp_data_dir / "memory_books" / f"{book.book_id}.json"
        assert file_path.exists()


class TestMemoryBookRead:
    """Tests for reading memory books."""

    def test_get_book(self, memory_book_manager):
        """Test getting a book by ID."""
        create_data = MemoryBookCreate(name="Test Book")
        created = memory_book_manager.create_book(create_data)

        retrieved = memory_book_manager.get_book(created.book_id)

        assert retrieved is not None
        assert retrieved.book_id == created.book_id
        assert retrieved.name == created.name

    def test_get_book_not_found(self, memory_book_manager):
        """Test getting a non-existent book."""
        result = memory_book_manager.get_book("nonexistent")
        assert result is None

    def test_list_books_empty(self, memory_book_manager):
        """Test listing books when none exist."""
        result = memory_book_manager.list_books()
        assert result == []

    def test_list_books(self, memory_book_manager):
        """Test listing all books."""
        memory_book_manager.create_book(MemoryBookCreate(name="Book 1"))
        memory_book_manager.create_book(MemoryBookCreate(name="Book 2"))

        result = memory_book_manager.list_books()

        assert len(result) == 2


class TestMemoryBookUpdate:
    """Tests for updating memory books."""

    def test_update_book_name(self, memory_book_manager):
        """Test updating book name."""
        book = memory_book_manager.create_book(
            MemoryBookCreate(name="Old Name")
        )

        updated = memory_book_manager.update_book(book.book_id, name="New Name")

        assert updated is not None
        assert updated.name == "New Name"

    def test_update_book_description(self, memory_book_manager):
        """Test updating book description."""
        book = memory_book_manager.create_book(
            MemoryBookCreate(name="Test", description="Old description")
        )

        updated = memory_book_manager.update_book(
            book.book_id, description="New description"
        )

        assert updated is not None
        assert updated.description == "New description"

    def test_update_nonexistent_book(self, memory_book_manager):
        """Test updating a non-existent book."""
        result = memory_book_manager.update_book("nonexistent", name="Test")
        assert result is None


class TestMemoryBookDelete:
    """Tests for deleting memory books."""

    def test_delete_book(self, memory_book_manager):
        """Test deleting a book."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))

        result = memory_book_manager.delete_book(book.book_id)

        assert result is True
        assert memory_book_manager.get_book(book.book_id) is None

    def test_delete_nonexistent_book(self, memory_book_manager):
        """Test deleting a non-existent book."""
        result = memory_book_manager.delete_book("nonexistent")
        assert result is False


class TestMemoryItems:
    """Tests for memory item operations."""

    def test_add_item(self, memory_book_manager):
        """Test adding an item to a book."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))

        item_create = MemoryItemCreate(
            target_type=MemoryItemType.WORD,
            target_id="serendipity",
            source_timeline_id="timeline_123",
            source_timecode=100.5,
            source_segment_text="It was pure serendipity.",
            user_notes="A happy accident",
            tags=["vocab", "gre"],
        )

        item = memory_book_manager.add_item(book.book_id, item_create)

        assert item is not None
        assert item.target_type == MemoryItemType.WORD
        assert item.target_id == "serendipity"
        assert item.user_notes == "A happy accident"
        assert "vocab" in item.tags

    def test_add_item_generates_id(self, memory_book_manager):
        """Test that item ID is auto-generated."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))

        item_create = MemoryItemCreate(
            target_type=MemoryItemType.WORD,
            target_id="test",
        )

        item = memory_book_manager.add_item(book.book_id, item_create)

        assert item.item_id is not None

    def test_add_item_to_nonexistent_book(self, memory_book_manager):
        """Test adding item to non-existent book."""
        item_create = MemoryItemCreate(
            target_type=MemoryItemType.WORD,
            target_id="test",
        )

        result = memory_book_manager.add_item("nonexistent", item_create)

        assert result is None

    def test_get_items(self, memory_book_manager):
        """Test getting all items from a book."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))

        for word in ["apple", "banana", "cherry"]:
            memory_book_manager.add_item(
                book.book_id,
                MemoryItemCreate(
                    target_type=MemoryItemType.WORD,
                    target_id=word,
                ),
            )

        items = memory_book_manager.get_items(book.book_id)

        assert items is not None
        assert len(items) == 3

    def test_get_items_nonexistent_book(self, memory_book_manager):
        """Test getting items from non-existent book."""
        result = memory_book_manager.get_items("nonexistent")
        assert result is None

    def test_get_item(self, memory_book_manager):
        """Test getting a specific item."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))
        item = memory_book_manager.add_item(
            book.book_id,
            MemoryItemCreate(
                target_type=MemoryItemType.WORD,
                target_id="test",
            ),
        )

        retrieved = memory_book_manager.get_item(book.book_id, item.item_id)

        assert retrieved is not None
        assert retrieved.item_id == item.item_id

    def test_get_item_not_found(self, memory_book_manager):
        """Test getting a non-existent item."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))

        result = memory_book_manager.get_item(book.book_id, "nonexistent")

        assert result is None

    def test_update_item(self, memory_book_manager):
        """Test updating an item."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))
        item = memory_book_manager.add_item(
            book.book_id,
            MemoryItemCreate(
                target_type=MemoryItemType.WORD,
                target_id="test",
                user_notes="Original note",
            ),
        )

        updated = memory_book_manager.update_item(
            book.book_id,
            item.item_id,
            user_notes="Updated note",
            tags=["new-tag"],
        )

        assert updated is not None
        assert updated.user_notes == "Updated note"
        assert "new-tag" in updated.tags

    def test_remove_item(self, memory_book_manager):
        """Test removing an item from a book."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))
        item = memory_book_manager.add_item(
            book.book_id,
            MemoryItemCreate(
                target_type=MemoryItemType.WORD,
                target_id="test",
            ),
        )

        result = memory_book_manager.remove_item(book.book_id, item.item_id)

        assert result is True
        assert memory_book_manager.get_item(book.book_id, item.item_id) is None

    def test_remove_nonexistent_item(self, memory_book_manager):
        """Test removing a non-existent item."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))

        result = memory_book_manager.remove_item(book.book_id, "nonexistent")

        assert result is False


class TestMemoryBookUtilities:
    """Tests for utility methods."""

    def test_get_default_book_creates(self, memory_book_manager):
        """Test that get_default_book creates one if none exists."""
        default = memory_book_manager.get_default_book()

        assert default is not None
        assert default.name == "My Collection"

    def test_get_default_book_returns_existing(self, memory_book_manager):
        """Test that get_default_book returns existing default."""
        # Get (create) default
        default1 = memory_book_manager.get_default_book()

        # Get again - should return same one
        default2 = memory_book_manager.get_default_book()

        assert default1.book_id == default2.book_id

    def test_find_item_by_target(self, memory_book_manager):
        """Test finding an item by target type and ID."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))
        memory_book_manager.add_item(
            book.book_id,
            MemoryItemCreate(
                target_type=MemoryItemType.WORD,
                target_id="serendipity",
            ),
        )

        found = memory_book_manager.find_item_by_target(
            book.book_id, "word", "serendipity"
        )

        assert found is not None
        assert found.target_id == "serendipity"

    def test_find_item_by_target_not_found(self, memory_book_manager):
        """Test finding non-existent item by target."""
        book = memory_book_manager.create_book(MemoryBookCreate(name="Test"))

        result = memory_book_manager.find_item_by_target(
            book.book_id, "word", "nonexistent"
        )

        assert result is None


class TestMemoryBookPersistence:
    """Tests for data persistence."""

    def test_reload_books(self, temp_data_dir, mock_config):
        """Test that books persist across manager instances."""
        # Create book with first manager
        with patch("app.services.memory_book_manager.get_config", return_value=mock_config):
            manager1 = MemoryBookManager()
            book = manager1.create_book(MemoryBookCreate(name="Persistent Book"))
            book_id = book.book_id

        # Create new manager instance and verify data loads
        with patch("app.services.memory_book_manager.get_config", return_value=mock_config):
            manager2 = MemoryBookManager()
            loaded = manager2.get_book(book_id)

            assert loaded is not None
            assert loaded.name == "Persistent Book"

    def test_reload_items(self, temp_data_dir, mock_config):
        """Test that items persist across manager instances."""
        # Create book and items with first manager
        with patch("app.services.memory_book_manager.get_config", return_value=mock_config):
            manager1 = MemoryBookManager()
            book = manager1.create_book(MemoryBookCreate(name="Test"))
            manager1.add_item(
                book.book_id,
                MemoryItemCreate(
                    target_type=MemoryItemType.WORD,
                    target_id="persistent_word",
                ),
            )
            book_id = book.book_id

        # Verify items load in new manager
        with patch("app.services.memory_book_manager.get_config", return_value=mock_config):
            manager2 = MemoryBookManager()
            items = manager2.get_items(book_id)

            assert items is not None
            assert len(items) == 1
            assert items[0].target_id == "persistent_word"
