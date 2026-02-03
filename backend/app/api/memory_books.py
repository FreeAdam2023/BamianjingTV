"""Memory Books API endpoints."""

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.models.memory_book import (
    MemoryBook,
    MemoryBookCreate,
    MemoryBookSummary,
    MemoryBookUpdate,
    MemoryItem,
    MemoryItemCreate,
    MemoryItemUpdate,
)
from app.services.memory_book_manager import MemoryBookManager
from app.workers.anki_export import AnkiExportWorker

router = APIRouter(prefix="/memory-books", tags=["memory-books"])

# These will be set by main.py during startup
_memory_book_manager: Optional[MemoryBookManager] = None
_anki_export_worker: Optional[AnkiExportWorker] = None


def set_memory_book_manager(manager: MemoryBookManager) -> None:
    """Set the memory book manager instance."""
    global _memory_book_manager
    _memory_book_manager = manager


def set_anki_export_worker(worker: AnkiExportWorker) -> None:
    """Set the Anki export worker instance."""
    global _anki_export_worker
    _anki_export_worker = worker


def get_manager() -> MemoryBookManager:
    """Get the memory book manager, raising if not initialized."""
    if _memory_book_manager is None:
        raise HTTPException(status_code=503, detail="Memory book manager not initialized")
    return _memory_book_manager


def get_anki_worker() -> AnkiExportWorker:
    """Get the Anki export worker, raising if not initialized."""
    if _anki_export_worker is None:
        raise HTTPException(status_code=503, detail="Anki export worker not initialized")
    return _anki_export_worker


# --- Memory Book Endpoints ---


@router.get("", response_model=List[MemoryBookSummary])
async def list_books():
    """List all memory books."""
    return get_manager().list_books()


@router.post("", response_model=MemoryBook)
async def create_book(data: MemoryBookCreate):
    """Create a new memory book."""
    return get_manager().create_book(data)


@router.get("/default", response_model=MemoryBook)
async def get_default_book():
    """Get or create the default memory book."""
    return get_manager().get_default_book()


@router.get("/{book_id}", response_model=MemoryBook)
async def get_book(book_id: str):
    """Get a memory book by ID."""
    book = get_manager().get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Memory book not found")
    return book


@router.patch("/{book_id}", response_model=MemoryBook)
async def update_book(book_id: str, data: MemoryBookUpdate):
    """Update a memory book's metadata."""
    book = get_manager().update_book(book_id, name=data.name, description=data.description)
    if not book:
        raise HTTPException(status_code=404, detail="Memory book not found")
    return book


@router.delete("/{book_id}")
async def delete_book(book_id: str):
    """Delete a memory book."""
    if not get_manager().delete_book(book_id):
        raise HTTPException(status_code=404, detail="Memory book not found")
    return {"status": "deleted", "book_id": book_id}


# --- Memory Item Endpoints ---


@router.get("/{book_id}/items", response_model=List[MemoryItem])
async def list_items(book_id: str):
    """List all items in a memory book."""
    items = get_manager().get_items(book_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Memory book not found")
    return items


@router.post("/{book_id}/items", response_model=MemoryItem)
async def add_item(book_id: str, data: MemoryItemCreate):
    """Add an item to a memory book."""
    item = get_manager().add_item(book_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Memory book not found")
    return item


@router.get("/{book_id}/items/{item_id}", response_model=MemoryItem)
async def get_item(book_id: str, item_id: str):
    """Get a specific item from a memory book."""
    item = get_manager().get_item(book_id, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{book_id}/items/{item_id}", response_model=MemoryItem)
async def update_item(book_id: str, item_id: str, data: MemoryItemUpdate):
    """Update an item's notes or tags."""
    item = get_manager().update_item(
        book_id, item_id, user_notes=data.user_notes, tags=data.tags
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/{book_id}/items/{item_id}")
async def delete_item(book_id: str, item_id: str):
    """Delete an item from a memory book."""
    if not get_manager().remove_item(book_id, item_id):
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "deleted", "item_id": item_id}


# --- Check if item exists ---


@router.get("/{book_id}/items/check/{target_type}/{target_id}")
async def check_item_exists(book_id: str, target_type: str, target_id: str):
    """Check if an item with the given target already exists in the book."""
    item = get_manager().find_item_by_target(book_id, target_type, target_id)
    return {
        "exists": item is not None,
        "item_id": item.item_id if item else None,
    }


# --- Anki Export Endpoint ---


@router.get("/{book_id}/export/anki")
async def export_anki(book_id: str):
    """Export a memory book as an Anki .apkg file."""
    book = get_manager().get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Memory book not found")

    if book.item_count == 0:
        raise HTTPException(status_code=400, detail="Memory book is empty")

    try:
        worker = get_anki_worker()
        output_path = worker.export_book(book)
        return FileResponse(
            path=output_path,
            filename=f"{book.name}.apkg",
            media_type="application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
