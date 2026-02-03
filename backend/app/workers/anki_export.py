"""Anki Export Worker - Generate .apkg files from memory books."""

import logging
import random
from pathlib import Path
from typing import List, Optional

from app.models.memory_book import MemoryBook, MemoryItem, MemoryItemType

logger = logging.getLogger(__name__)

try:
    import genanki
    GENANKI_AVAILABLE = True
except ImportError:
    GENANKI_AVAILABLE = False
    logger.warning("genanki not installed. Anki export will not be available.")


# Anki model IDs (must be unique and consistent)
WORD_MODEL_ID = 1607392319
ENTITY_MODEL_ID = 1607392320


def _create_word_model() -> "genanki.Model":
    """Create Anki model for word cards."""
    return genanki.Model(
        WORD_MODEL_ID,
        "Hardcore Player - Word",
        fields=[
            {"name": "Word"},
            {"name": "Pronunciation"},
            {"name": "Definition"},
            {"name": "Examples"},
            {"name": "Context"},
            {"name": "Notes"},
        ],
        templates=[
            {
                "name": "Recognition",
                "qfmt": """
<div class="word">{{Word}}</div>
<div class="context">{{Context}}</div>
""",
                "afmt": """
{{FuseSides}}
<hr id="answer">
<div class="pronunciation">{{Pronunciation}}</div>
<div class="definition">{{Definition}}</div>
<div class="examples">{{Examples}}</div>
{{#Notes}}<div class="notes">📝 {{Notes}}</div>{{/Notes}}
""",
            },
            {
                "name": "Recall",
                "qfmt": """
<div class="definition">{{Definition}}</div>
<div class="examples">{{Examples}}</div>
""",
                "afmt": """
{{FuseSides}}
<hr id="answer">
<div class="word">{{Word}}</div>
<div class="pronunciation">{{Pronunciation}}</div>
<div class="context">{{Context}}</div>
{{#Notes}}<div class="notes">📝 {{Notes}}</div>{{/Notes}}
""",
            },
        ],
        css="""
.card {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 18px;
    text-align: center;
    color: #333;
    background-color: #f9f9f9;
    padding: 20px;
}
.word {
    font-size: 32px;
    font-weight: bold;
    color: #2563eb;
    margin-bottom: 16px;
}
.pronunciation {
    font-size: 20px;
    color: #666;
    font-style: italic;
    margin-bottom: 12px;
}
.definition {
    font-size: 20px;
    margin-bottom: 16px;
}
.examples {
    font-size: 16px;
    color: #555;
    text-align: left;
    background: #fff;
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 12px;
}
.context {
    font-size: 16px;
    color: #888;
    font-style: italic;
    margin-top: 12px;
}
.notes {
    font-size: 14px;
    color: #666;
    margin-top: 16px;
    padding: 8px;
    background: #fffef0;
    border-radius: 4px;
}
""",
    )


def _create_entity_model() -> "genanki.Model":
    """Create Anki model for entity cards."""
    return genanki.Model(
        ENTITY_MODEL_ID,
        "Hardcore Player - Entity",
        fields=[
            {"name": "Name"},
            {"name": "Type"},
            {"name": "Description"},
            {"name": "WikipediaURL"},
            {"name": "Context"},
            {"name": "Notes"},
        ],
        templates=[
            {
                "name": "Entity Card",
                "qfmt": """
<div class="entity-name">{{Name}}</div>
<div class="entity-type">{{Type}}</div>
<div class="context">{{Context}}</div>
""",
                "afmt": """
{{FuseSides}}
<hr id="answer">
<div class="description">{{Description}}</div>
{{#WikipediaURL}}<div class="wiki-link"><a href="{{WikipediaURL}}">Wikipedia →</a></div>{{/WikipediaURL}}
{{#Notes}}<div class="notes">📝 {{Notes}}</div>{{/Notes}}
""",
            },
        ],
        css="""
.card {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 18px;
    text-align: center;
    color: #333;
    background-color: #f9f9f9;
    padding: 20px;
}
.entity-name {
    font-size: 28px;
    font-weight: bold;
    color: #059669;
    margin-bottom: 8px;
}
.entity-type {
    font-size: 14px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 16px;
}
.description {
    font-size: 18px;
    text-align: left;
    line-height: 1.5;
    margin-bottom: 16px;
}
.context {
    font-size: 16px;
    color: #888;
    font-style: italic;
    margin-top: 12px;
}
.wiki-link {
    margin-top: 12px;
}
.wiki-link a {
    color: #2563eb;
    text-decoration: none;
}
.notes {
    font-size: 14px;
    color: #666;
    margin-top: 16px;
    padding: 8px;
    background: #fffef0;
    border-radius: 4px;
}
""",
    )


class AnkiExportWorker:
    """Worker to export memory books to Anki .apkg files."""

    def __init__(self, output_dir: Optional[Path] = None):
        if not GENANKI_AVAILABLE:
            raise RuntimeError("genanki is not installed. Run: pip install genanki")
        self.output_dir = output_dir or Path("./data/exports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.word_model = _create_word_model()
        self.entity_model = _create_entity_model()

    def _item_to_note(self, item: MemoryItem) -> Optional["genanki.Note"]:
        """Convert a memory item to an Anki note."""
        fields = item.to_anki_fields()

        if item.target_type == MemoryItemType.WORD:
            return genanki.Note(
                model=self.word_model,
                fields=[
                    fields.get("word", ""),
                    fields.get("pronunciation", ""),
                    fields.get("definition", ""),
                    fields.get("examples", ""),
                    fields.get("context", ""),
                    fields.get("notes", ""),
                ],
            )
        elif item.target_type == MemoryItemType.ENTITY:
            return genanki.Note(
                model=self.entity_model,
                fields=[
                    fields.get("name", ""),
                    fields.get("type", ""),
                    fields.get("description", ""),
                    fields.get("wikipedia_url", ""),
                    fields.get("context", ""),
                    fields.get("notes", ""),
                ],
            )
        else:
            # Observation items are not exported to Anki
            return None

    def export_book(self, book: MemoryBook, filename: Optional[str] = None) -> Path:
        """
        Export a memory book to an Anki .apkg file.

        Args:
            book: The memory book to export
            filename: Optional output filename (without extension)

        Returns:
            Path to the generated .apkg file
        """
        # Generate unique deck ID based on book ID
        deck_id = int(book.book_id, 16) if len(book.book_id) <= 8 else random.randint(
            1 << 30, 1 << 31
        )

        deck = genanki.Deck(deck_id, f"Hardcore Player - {book.name}")

        # Add notes for each item
        word_count = 0
        entity_count = 0
        for item in book.items:
            note = self._item_to_note(item)
            if note:
                deck.add_note(note)
                if item.target_type == MemoryItemType.WORD:
                    word_count += 1
                elif item.target_type == MemoryItemType.ENTITY:
                    entity_count += 1

        # Generate package
        package = genanki.Package(deck)

        # Determine output path
        if filename is None:
            filename = f"{book.book_id}_{book.name.replace(' ', '_')}"
        output_path = self.output_dir / f"{filename}.apkg"

        # Write file
        package.write_to_file(str(output_path))

        logger.info(
            f"Exported memory book '{book.name}' to {output_path} "
            f"({word_count} words, {entity_count} entities)"
        )

        return output_path

    def export_items(
        self, items: List[MemoryItem], deck_name: str, filename: str
    ) -> Path:
        """
        Export a list of items to an Anki .apkg file.

        Args:
            items: List of memory items to export
            deck_name: Name for the Anki deck
            filename: Output filename (without extension)

        Returns:
            Path to the generated .apkg file
        """
        deck_id = random.randint(1 << 30, 1 << 31)
        deck = genanki.Deck(deck_id, deck_name)

        for item in items:
            note = self._item_to_note(item)
            if note:
                deck.add_note(note)

        package = genanki.Package(deck)
        output_path = self.output_dir / f"{filename}.apkg"
        package.write_to_file(str(output_path))

        logger.info(f"Exported {len(items)} items to {output_path}")
        return output_path
