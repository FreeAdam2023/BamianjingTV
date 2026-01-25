"""Thumbnail generation worker for YouTube-style video covers."""

import base64
import hashlib
import httpx
from pathlib import Path
from typing import Optional
from loguru import logger

from app.config import settings


class ThumbnailWorker:
    """Worker for generating YouTube-style video thumbnails using AI."""

    def __init__(self):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url

        # Detect if using Grok API (xAI)
        self.is_grok = "x.ai" in self.base_url.lower()

        # Image generation settings
        if self.is_grok:
            # Use Grok's image generation (Aurora model)
            self.image_model = "grok-2-image"
        else:
            # Fallback to DALL-E
            self.image_model = "dall-e-3"

    async def generate_prompt_from_content(
        self,
        title: str,
        subtitles: list[str],
        language: str = "en",
    ) -> str:
        """Generate an image prompt from video content using LLM.

        Args:
            title: Video title
            subtitles: List of subtitle texts
            language: Language hint

        Returns:
            Image generation prompt
        """
        # Take first few subtitles for context
        content_sample = " ".join(subtitles[:10])[:500]

        system_prompt = """You are a YouTube thumbnail designer. Generate a concise image prompt for DALL-E to create an eye-catching YouTube thumbnail.

Rules:
- Focus on visual elements that attract clicks
- Include dramatic lighting, bold colors
- Suggest facial expressions or reactions if relevant
- Keep it under 200 words
- Do NOT include any text/words in the image description
- Make it visually striking and professional

Output ONLY the image prompt, nothing else."""

        user_prompt = f"""Create a YouTube thumbnail prompt for:

Title: {title}

Content sample: {content_sample}

Generate a dramatic, eye-catching thumbnail image prompt."""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 300,
                        "temperature": 0.8,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Failed to generate prompt: {e}")
            # Fallback to a generic prompt
            return f"Professional YouTube thumbnail, dramatic lighting, bold colors, modern design, high quality, 4K, cinematic"

    async def generate_thumbnail(
        self,
        prompt: str,
        output_path: Path,
    ) -> Optional[Path]:
        """Generate thumbnail image using Grok or DALL-E.

        Args:
            prompt: Image generation prompt
            output_path: Where to save the image

        Returns:
            Path to generated image or None if failed
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Enhanced prompt for YouTube style
        full_prompt = f"YouTube video thumbnail style, {prompt}, no text, no words, no letters, photorealistic, high contrast, vibrant colors, professional quality"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if self.is_grok:
                    # Grok API (xAI) - uses same endpoint format
                    response = await client.post(
                        f"{self.base_url}/images/generations",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.image_model,
                            "prompt": full_prompt,
                            "n": 1,
                            "response_format": "b64_json",
                        },
                    )
                else:
                    # OpenAI DALL-E API
                    response = await client.post(
                        f"{self.base_url}/images/generations",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.image_model,
                            "prompt": full_prompt,
                            "n": 1,
                            "size": "1792x1024",
                            "quality": "standard",
                            "response_format": "b64_json",
                        },
                    )

                response.raise_for_status()
                data = response.json()

                # Decode and save image
                image_data = base64.b64decode(data["data"][0]["b64_json"])
                with open(output_path, "wb") as f:
                    f.write(image_data)

                logger.info(f"Generated thumbnail using {self.image_model}: {output_path}")
                return output_path

        except httpx.HTTPStatusError as e:
            logger.error(f"Image API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.exception(f"Failed to generate thumbnail: {e}")
            return None

    async def generate_for_timeline(
        self,
        title: str,
        subtitles: list[str],
        output_dir: Path,
        filename: Optional[str] = None,
    ) -> Optional[Path]:
        """Generate a thumbnail for a timeline.

        Args:
            title: Video title
            subtitles: List of English subtitles
            output_dir: Directory to save thumbnail
            filename: Optional filename (default: thumbnail_<hash>.png)

        Returns:
            Path to generated thumbnail or None
        """
        # Generate prompt from content
        prompt = await self.generate_prompt_from_content(title, subtitles)
        logger.info(f"Generated prompt: {prompt[:100]}...")

        # Generate unique filename if not provided
        if not filename:
            content_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            filename = f"thumbnail_{content_hash}.png"

        output_path = Path(output_dir) / filename

        return await self.generate_thumbnail(prompt, output_path)
