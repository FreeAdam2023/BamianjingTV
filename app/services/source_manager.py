"""Source manager service for MirrorFlow v2."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

from app.config import settings
from app.models.source import Source, SourceType, SourceCreate, SourceUpdate


class SourceManager:
    """Manages source lifecycle with JSON file persistence."""

    def __init__(self):
        self.sources: Dict[str, Source] = {}
        self._load_sources()

    def _load_sources(self) -> None:
        """Load sources from JSON file on startup."""
        sources_file = settings.sources_file
        if not sources_file.exists():
            logger.info("No existing sources file found")
            return

        try:
            with open(sources_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for source_data in data.get("sources", []):
                source = Source(**source_data)
                self.sources[source.source_id] = source

            logger.info(f"Loaded {len(self.sources)} sources")
        except Exception as e:
            logger.error(f"Failed to load sources from {sources_file}: {e}")

    def _save_sources(self) -> None:
        """Save all sources to JSON file."""
        sources_file = settings.sources_file
        sources_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "sources": [
                source.model_dump(mode="json")
                for source in self.sources.values()
            ]
        }

        with open(sources_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def create_source(self, source_create: SourceCreate) -> Source:
        """Create a new source."""
        if source_create.source_id in self.sources:
            raise ValueError(f"Source '{source_create.source_id}' already exists")

        source = Source(
            source_id=source_create.source_id,
            source_type=source_create.source_type,
            sub_type=source_create.sub_type,
            display_name=source_create.display_name,
            fetcher=source_create.fetcher,
            config=source_create.config,
            enabled=source_create.enabled,
            default_pipelines=source_create.default_pipelines,
            created_at=datetime.now(),
        )

        self.sources[source.source_id] = source
        self._save_sources()
        logger.info(f"Created source: {source.source_id} ({source.display_name})")
        return source

    def get_source(self, source_id: str) -> Optional[Source]:
        """Get a source by ID."""
        return self.sources.get(source_id)

    def list_sources(
        self,
        source_type: Optional[SourceType] = None,
        enabled_only: bool = False,
        limit: int = 100,
    ) -> List[Source]:
        """List sources with optional filtering."""
        sources = list(self.sources.values())

        if source_type:
            sources = [s for s in sources if s.source_type == source_type]

        if enabled_only:
            sources = [s for s in sources if s.enabled]

        # Sort by creation time, newest first
        sources.sort(key=lambda s: s.created_at, reverse=True)

        return sources[:limit]

    def update_source(
        self,
        source_id: str,
        source_update: SourceUpdate,
    ) -> Optional[Source]:
        """Update an existing source."""
        source = self.sources.get(source_id)
        if not source:
            return None

        # Apply updates
        update_data = source_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(source, field, value)

        self._save_sources()
        logger.info(f"Updated source: {source_id}")
        return source

    def delete_source(self, source_id: str) -> bool:
        """Delete a source."""
        source = self.sources.pop(source_id, None)
        if not source:
            return False

        self._save_sources()
        logger.info(f"Deleted source: {source_id}")
        return True

    def update_last_fetched(self, source_id: str) -> Optional[Source]:
        """Update the last_fetched_at timestamp for a source."""
        source = self.sources.get(source_id)
        if not source:
            return None

        source.last_fetched_at = datetime.now()
        self._save_sources()
        return source

    def increment_item_count(self, source_id: str, count: int = 1) -> Optional[Source]:
        """Increment the item count for a source."""
        source = self.sources.get(source_id)
        if not source:
            return None

        source.item_count += count
        self._save_sources()
        return source

    def get_sources_by_type(self) -> Dict[SourceType, List[Source]]:
        """Get sources grouped by type."""
        result: Dict[SourceType, List[Source]] = {}

        for source in self.sources.values():
            if source.source_type not in result:
                result[source.source_type] = []
            result[source.source_type].append(source)

        return result

    def get_stats(self) -> Dict:
        """Get source statistics."""
        stats = {
            "total": len(self.sources),
            "by_type": {},
            "enabled": sum(1 for s in self.sources.values() if s.enabled),
        }

        for source_type in SourceType:
            count = sum(
                1 for s in self.sources.values()
                if s.source_type == source_type
            )
            if count > 0:
                stats["by_type"][source_type.value] = count

        return stats
