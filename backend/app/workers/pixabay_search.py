"""Pixabay image search and download for lofi background images."""

from pathlib import Path
from typing import List
from uuid import uuid4

import httpx
from loguru import logger

from app.config import settings

PIXABAY_API_URL = "https://pixabay.com/api/"


async def search_pixabay(
    query: str,
    per_page: int = 20,
    image_type: str = "photo",
    orientation: str = "horizontal",
    min_width: int = 1920,
) -> List[dict]:
    """Search Pixabay for free images.

    Returns a list of dicts with: id, preview_url, large_url, tags, width, height.
    """
    if not settings.pixabay_api_key:
        raise ValueError("PIXABAY_API_KEY not configured")

    params = {
        "key": settings.pixabay_api_key,
        "q": query,
        "image_type": image_type,
        "orientation": orientation,
        "min_width": min_width,
        "per_page": per_page,
        "safesearch": "true",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(PIXABAY_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

    results = []
    for hit in data.get("hits", []):
        results.append({
            "id": str(hit["id"]),
            "preview_url": hit.get("webformatURL", ""),
            "large_url": hit.get("largeImageURL", ""),
            "tags": hit.get("tags", ""),
            "width": hit.get("imageWidth", 0),
            "height": hit.get("imageHeight", 0),
        })
    return results


async def download_pixabay_image(
    pixabay_id: str,
    url: str,
    filename: str | None = None,
) -> Path:
    """Download a Pixabay image to lofi_images_dir.

    Returns the saved file path.
    """
    if not filename:
        ext = url.rsplit(".", 1)[-1].split("?")[0] if "." in url else "jpg"
        filename = f"pixabay_{pixabay_id}_{uuid4().hex[:6]}.{ext}"

    dest = settings.lofi_images_dir / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        dest.write_bytes(response.content)

    logger.info(f"Downloaded Pixabay image {pixabay_id} → {dest}")
    return dest
