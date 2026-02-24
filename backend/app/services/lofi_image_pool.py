"""Lofi Image Pool — manages background images for lofi video generation."""

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from app.config import get_config
from app.models.lofi import (
    ImageSource,
    ImageStatus,
    LofiPoolImage,
    LofiTheme,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class LofiImagePool:
    """Manages a pool of background images with approval workflow."""

    def __init__(self) -> None:
        config = get_config()
        self._storage_dir = config.lofi_images_dir
        self._pool_file = self._storage_dir / "pool.json"
        self._images: Dict[str, LofiPoolImage] = {}
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        """Load pool from disk."""
        if self._pool_file.exists():
            try:
                data = json.loads(self._pool_file.read_text(encoding="utf-8"))
                for item in data:
                    img = LofiPoolImage(**item)
                    self._images[img.id] = img
                logger.debug(f"Loaded {len(self._images)} images from pool")
            except Exception as e:
                logger.warning(f"Failed to load image pool: {e}")
                self._images = {}

    def _save(self) -> None:
        """Persist pool to disk."""
        data = [img.model_dump(mode="json") for img in self._images.values()]
        self._pool_file.write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )

    def add_image(self, image: LofiPoolImage) -> LofiPoolImage:
        """Add an image to the pool."""
        self._images[image.id] = image
        self._save()
        return image

    def get_image(self, image_id: str) -> Optional[LofiPoolImage]:
        """Get an image by ID."""
        return self._images.get(image_id)

    def list_images(
        self,
        status: Optional[ImageStatus] = None,
        theme: Optional[LofiTheme] = None,
        source: Optional[ImageSource] = None,
    ) -> List[LofiPoolImage]:
        """List images with optional filters."""
        results = list(self._images.values())
        if status is not None:
            results = [img for img in results if img.status == status]
        if theme is not None:
            results = [img for img in results if theme in img.themes]
        if source is not None:
            results = [img for img in results if img.source == source]
        return sorted(results, key=lambda i: i.created_at, reverse=True)

    def update_status(self, image_id: str, status: ImageStatus) -> Optional[LofiPoolImage]:
        """Update an image's approval status."""
        img = self._images.get(image_id)
        if not img:
            return None
        img.status = status
        self._save()
        return img

    def update_themes(self, image_id: str, themes: List[LofiTheme]) -> Optional[LofiPoolImage]:
        """Update an image's theme tags."""
        img = self._images.get(image_id)
        if not img:
            return None
        img.themes = themes
        self._save()
        return img

    def delete_image(self, image_id: str) -> bool:
        """Remove an image from the pool and delete the file."""
        img = self._images.pop(image_id, None)
        if not img:
            return False
        file_path = self._storage_dir / img.filename
        if file_path.exists():
            file_path.unlink()
        self._save()
        return True

    def get_random_approved(self, theme: Optional[LofiTheme] = None) -> Optional[LofiPoolImage]:
        """Get a random approved image, optionally matching a theme."""
        candidates = [
            img for img in self._images.values()
            if img.status == ImageStatus.APPROVED
        ]
        if theme is not None:
            themed = [img for img in candidates if theme in img.themes]
            if themed:
                candidates = themed
        if not candidates:
            return None
        return random.choice(candidates)

    def sync_from_disk(self) -> int:
        """Scan lofi_images_dir for files not yet in the pool and add them as PENDING/UPLOAD."""
        known_filenames = {img.filename for img in self._images.values()}
        added = 0
        if not self._storage_dir.exists():
            return 0
        for path in sorted(self._storage_dir.iterdir()):
            if path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if path.name in known_filenames:
                continue
            img = LofiPoolImage(
                filename=path.name,
                source=ImageSource.UPLOAD,
                status=ImageStatus.PENDING,
            )
            self._images[img.id] = img
            added += 1
        if added > 0:
            self._save()
            logger.info(f"Synced {added} new images from disk into pool")
        return added
