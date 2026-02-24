"""AI image generation for lofi background images."""

import base64
from pathlib import Path
from typing import Optional
from uuid import uuid4

import httpx
from loguru import logger

from app.config import settings
from app.models.lofi import LofiTheme

IMAGE_PROMPTS: dict[str, str] = {
    "lofi_hip_hop": "cozy bedroom at night, warm lamp, rain on window, lo-fi anime aesthetic, 4K",
    "jazz": "dimly lit jazz bar, piano, warm amber lighting, vintage aesthetic, 4K",
    "ambient": "serene mountain lake at dawn, misty, ethereal atmosphere, 4K",
    "chillhop": "rooftop terrace at sunset, city skyline, warm golden hour, 4K",
    "study": "peaceful library corner, stacked books, warm desk lamp, 4K",
    "sleep": "moonlit bedroom, soft blue tones, stars through window, dreamy, 4K",
    "coffee_shop": "cozy coffee shop interior, steaming cup, rainy window, warm tones, 4K",
    "rain": "rainy city street at night, neon reflections, puddles, cinematic, 4K",
    "night": "late night city view from window, neon lights, moody atmosphere, 4K",
    "piano": "grand piano in candlelit room, elegant, warm tones, classical, 4K",
    "guitar": "acoustic guitar on porch, sunset, countryside, warm golden light, 4K",
}


def _theme_to_image_prompt(theme: LofiTheme) -> str:
    """Get the default image generation prompt for a theme."""
    return IMAGE_PROMPTS.get(theme.value, IMAGE_PROMPTS["lofi_hip_hop"])


async def generate_lofi_image(
    theme: LofiTheme,
    custom_prompt: Optional[str] = None,
) -> Path:
    """Generate a background image using AI (dall-e-3 or grok-2-image).

    Returns the saved file path.
    """
    if not settings.image_model:
        raise ValueError("image_model not configured (set IMAGE_MODEL env var)")
    if not settings.llm_api_key:
        raise ValueError("llm_api_key not configured")

    prompt = custom_prompt or _theme_to_image_prompt(theme)
    filename = f"ai_{theme.value}_{uuid4().hex[:8]}.png"
    dest = settings.lofi_images_dir / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.llm_base_url}/images/generations",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.image_model,
                "prompt": prompt,
                "n": 1,
                "size": "1792x1024",
                "response_format": "url",
            },
        )
        response.raise_for_status()
        data = response.json()

    image_data = data["data"][0]

    if "url" in image_data and image_data["url"]:
        # Download from URL
        async with httpx.AsyncClient(timeout=60.0) as client:
            img_response = await client.get(image_data["url"])
            img_response.raise_for_status()
            dest.write_bytes(img_response.content)
    elif "b64_json" in image_data:
        # Decode base64
        dest.write_bytes(base64.b64decode(image_data["b64_json"]))
    else:
        raise RuntimeError("No image data in API response")

    logger.info(f"Generated AI image for theme {theme.value} → {dest}")
    return dest
