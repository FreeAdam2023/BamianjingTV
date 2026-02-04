"""Item manager service for SceneMind."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import uuid
from loguru import logger

from app.config import settings
from app.models.source import SourceType
from app.models.item import Item, ItemStatus, ItemCreate, PipelineStatus


class ItemManager:
    """Manages item lifecycle with directory-based storage."""

    def __init__(self):
        self.items: Dict[str, Item] = {}
        self._load_items()

    def _get_item_path(self, source_type: SourceType, source_id: str, item_id: str) -> Path:
        """Get the file path for an item."""
        return settings.items_dir / source_type.value / source_id / f"{item_id}.json"

    def _get_source_items_dir(self, source_type: SourceType, source_id: str) -> Path:
        """Get the directory for a source's items."""
        return settings.items_dir / source_type.value / source_id

    def _load_items(self) -> None:
        """Load all items from disk on startup."""
        items_dir = settings.items_dir
        if not items_dir.exists():
            logger.info("No existing items directory found")
            return

        loaded = 0
        for type_dir in items_dir.iterdir():
            if not type_dir.is_dir():
                continue

            for source_dir in type_dir.iterdir():
                if not source_dir.is_dir():
                    continue

                for item_file in source_dir.glob("*.json"):
                    try:
                        with open(item_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        item = Item(**data)
                        self.items[item.item_id] = item
                        loaded += 1
                    except Exception as e:
                        logger.error(f"Failed to load item from {item_file}: {e}")

        logger.info(f"Loaded {loaded} items")

    def _save_item(self, item: Item) -> None:
        """Save an item to disk."""
        item_path = self._get_item_path(item.source_type, item.source_id, item.item_id)
        item_path.parent.mkdir(parents=True, exist_ok=True)

        with open(item_path, "w", encoding="utf-8") as f:
            json.dump(item.model_dump(mode="json"), f, indent=2, ensure_ascii=False, default=str)

    def create_item(self, item_create: ItemCreate) -> Item:
        """Create a new item."""
        # Generate unique item ID
        item_id = f"item_{str(uuid.uuid4())[:8]}"

        # Check for duplicate URL within the same source
        existing = self.get_item_by_url(item_create.source_id, item_create.original_url)
        if existing:
            logger.warning(f"Item already exists for URL: {item_create.original_url}")
            return existing

        item = Item(
            item_id=item_id,
            source_type=item_create.source_type,
            source_id=item_create.source_id,
            original_url=item_create.original_url,
            original_title=item_create.original_title,
            original_description=item_create.original_description,
            original_thumbnail=item_create.original_thumbnail,
            duration=item_create.duration,
            published_at=item_create.published_at,
            status=ItemStatus.DISCOVERED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.items[item.item_id] = item
        self._save_item(item)
        logger.info(f"Created item: {item.item_id} ({item.original_title[:50]}...)")
        return item

    def get_item(self, item_id: str) -> Optional[Item]:
        """Get an item by ID."""
        return self.items.get(item_id)

    def get_item_by_url(self, source_id: str, url: str) -> Optional[Item]:
        """Get an item by source ID and URL."""
        for item in self.items.values():
            if item.source_id == source_id and item.original_url == url:
                return item
        return None

    def list_items(
        self,
        source_type: Optional[SourceType] = None,
        source_id: Optional[str] = None,
        status: Optional[ItemStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Item]:
        """List items with optional filtering."""
        items = list(self.items.values())

        if source_type:
            items = [i for i in items if i.source_type == source_type]

        if source_id:
            items = [i for i in items if i.source_id == source_id]

        if status:
            items = [i for i in items if i.status == status]

        # Sort by creation time, newest first
        items.sort(key=lambda i: i.created_at, reverse=True)

        return items[offset:offset + limit]

    def delete_item(self, item_id: str) -> bool:
        """Delete an item."""
        item = self.items.pop(item_id, None)
        if not item:
            return False

        # Delete file
        item_path = self._get_item_path(item.source_type, item.source_id, item_id)
        if item_path.exists():
            item_path.unlink()

        logger.info(f"Deleted item: {item_id}")
        return True

    def update_pipeline_status(
        self,
        item_id: str,
        pipeline_id: str,
        status: str,
        progress: float = None,
        job_id: str = None,
        error: str = None,
    ) -> Optional[Item]:
        """Update pipeline status for an item."""
        item = self.items.get(item_id)
        if not item:
            return None

        item.update_pipeline_status(
            pipeline_id=pipeline_id,
            status=status,
            progress=progress,
            job_id=job_id,
            error=error,
        )

        self._save_item(item)
        return item

    def get_items_by_source(self, source_id: str) -> List[Item]:
        """Get all items for a source."""
        return [i for i in self.items.values() if i.source_id == source_id]

    def update_item_status(self, item_id: str, status: ItemStatus) -> Optional[Item]:
        """Update item status."""
        item = self.items.get(item_id)
        if not item:
            return None

        item.status = status
        item.updated_at = datetime.now()
        self._save_item(item)
        logger.info(f"Updated item {item_id} status to {status.value}")
        return item

    def get_recent_items(self, hours: int = 24) -> List[Item]:
        """Get items created within the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        items = [i for i in self.items.values() if i.created_at >= cutoff]
        items.sort(key=lambda i: i.created_at, reverse=True)
        return items

    def get_fanout_status(self, item_id: str) -> Optional[Dict]:
        """Get fan-out status for an item (all pipeline statuses)."""
        item = self.items.get(item_id)
        if not item:
            return None

        return {
            "item_id": item.item_id,
            "status": item.status.value,
            "pipelines": {
                pid: {
                    "status": ps.status,
                    "progress": ps.progress,
                    "job_id": ps.job_id,
                    "error": ps.error,
                    "started_at": ps.started_at.isoformat() if ps.started_at else None,
                    "completed_at": ps.completed_at.isoformat() if ps.completed_at else None,
                }
                for pid, ps in item.pipelines.items()
            }
        }

    def get_stats(self) -> Dict:
        """Get item statistics."""
        stats = {
            "total": len(self.items),
            "by_status": {},
            "by_source_type": {},
        }

        for status in ItemStatus:
            count = sum(1 for i in self.items.values() if i.status == status)
            if count > 0:
                stats["by_status"][status.value] = count

        for source_type in SourceType:
            count = sum(1 for i in self.items.values() if i.source_type == source_type)
            if count > 0:
                stats["by_source_type"][source_type.value] = count

        return stats

    def get_overview_by_source_type(self) -> Dict[str, Dict]:
        """Get overview statistics grouped by source type."""
        result = {}
        now = datetime.now()
        last_24h = now - timedelta(hours=24)

        for source_type in SourceType:
            type_items = [i for i in self.items.values() if i.source_type == source_type]

            if not type_items:
                continue

            # Count items created in last 24 hours
            new_items_24h = sum(1 for i in type_items if i.created_at >= last_24h)

            # Count active pipelines (processing)
            active_pipelines = 0
            for item in type_items:
                active_pipelines += sum(
                    1 for ps in item.pipelines.values()
                    if ps.status == "processing"
                )

            # Get unique sources
            sources = set(i.source_id for i in type_items)

            result[source_type.value] = {
                "source_count": len(sources),
                "item_count": len(type_items),
                "new_items_24h": new_items_24h,
                "active_pipelines": active_pipelines,
            }

        return result
