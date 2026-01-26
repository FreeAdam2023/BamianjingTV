"""Thumbnail generation worker for YouTube-style video covers."""

import base64
import hashlib
import httpx
import io
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger

from app.config import settings

# YouTube thumbnail dimensions
YOUTUBE_WIDTH = 1280
YOUTUBE_HEIGHT = 720


class ThumbnailWorker:
    """Worker for generating YouTube-style video thumbnails using AI."""

    def __init__(self):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url

        # Detect if using Grok API (xAI)
        self.is_grok = "x.ai" in self.base_url.lower()

        # Image generation settings from config
        # If config specifies a model, use it; otherwise auto-detect
        if settings.image_model:
            self.image_model = settings.image_model
            self.enabled = True
        elif self.is_grok:
            # Use Grok's Aurora image generation model
            self.image_model = "grok-2-image-1212"
            self.enabled = True
        else:
            # Fallback to DALL-E for OpenAI
            self.image_model = "dall-e-3"
            self.enabled = True

    async def generate_clickbait_title(
        self,
        title: str,
        subtitles: list[str],
    ) -> Tuple[str, str]:
        """Generate clickbait Chinese titles for thumbnail.

        Args:
            title: Video title
            subtitles: List of subtitle texts

        Returns:
            Tuple of (main_title, sub_title) in Chinese
        """
        content_sample = " ".join(subtitles[:15])[:800]

        system_prompt = """你是一个YouTube视频封面标题设计师。根据视频内容生成两行博眼球的中文标题。

规则：
- 主标题：6-10个字，黄色大字，要震撼、吸引点击
- 副标题：6-12个字，白色大字，补充说明
- 风格：新闻头条、震撼、引发好奇
- 使用繁体中文
- 可以稍微夸张但不要虚假

示例：
主标题：你就是左翼走狗
副标题：上任來最大衝突

主标题：川普震怒開除
副标题：FBI局長當場傻眼

只输出JSON格式：
{"main": "主标题", "sub": "副标题"}"""

        user_prompt = f"""视频标题：{title}

视频内容摘要：{content_sample}

生成博眼球的中文封面标题："""

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
                        "max_tokens": 200,
                        "temperature": 0.9,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Parse JSON response
                import json
                # Handle potential markdown code blocks
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                titles = json.loads(content)
                return titles.get("main", "精彩內容"), titles.get("sub", "不容錯過")

        except Exception as e:
            logger.error(f"Failed to generate clickbait title: {e}")
            return "精彩內容", "不容錯過"

    async def generate_image_prompt(
        self,
        title: str,
        subtitles: list[str],
    ) -> str:
        """Generate an image prompt for the background.

        Args:
            title: Video title
            subtitles: List of subtitle texts

        Returns:
            Image generation prompt
        """
        content_sample = " ".join(subtitles[:10])[:500]

        system_prompt = """You are a YouTube thumbnail designer. Generate a concise image prompt for creating a dramatic background image.

Rules:
- Focus on people, faces, expressions, or dramatic scenes
- Include dramatic lighting, high contrast
- Describe specific facial expressions (shocked, angry, pointing, etc.)
- DO NOT include any text/words in the image
- Make it visually striking for YouTube
- Keep it under 100 words

Output ONLY the image prompt, nothing else."""

        user_prompt = f"""Create a thumbnail background image prompt for:

Title: {title}

Content: {content_sample}

Generate a dramatic image prompt (no text in image):"""

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
                        "max_tokens": 200,
                        "temperature": 0.8,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Failed to generate image prompt: {e}")
            return "Professional person speaking at podium, dramatic lighting, high contrast, news broadcast style"

    async def generate_base_image(
        self,
        prompt: str,
    ) -> Optional[bytes]:
        """Generate base image using AI.

        Args:
            prompt: Image generation prompt

        Returns:
            Image bytes or None if failed
        """
        if not self.enabled:
            logger.warning("Thumbnail generation is disabled.")
            return None

        full_prompt = f"{prompt}, no text, no words, no letters, photorealistic, high contrast, YouTube thumbnail style, 16:9 aspect ratio"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                if self.is_grok:
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
                return base64.b64decode(data["data"][0]["b64_json"])

        except httpx.HTTPStatusError as e:
            logger.error(f"Image API error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.exception(f"Failed to generate base image: {e}")
            return None

    def add_text_overlay(
        self,
        image_bytes: bytes,
        main_title: str,
        sub_title: str,
        badge_text: str = "中英對照",
    ) -> bytes:
        """Add text overlays to the thumbnail image.

        Args:
            image_bytes: Base image bytes
            main_title: Main title (yellow text)
            sub_title: Sub title (white text on blue bar)
            badge_text: Corner badge text

        Returns:
            Final image bytes
        """
        from PIL import Image, ImageDraw, ImageFont
        import os

        # Load image
        img = Image.open(io.BytesIO(image_bytes))

        # Resize to YouTube dimensions
        img = img.resize((YOUTUBE_WIDTH, YOUTUBE_HEIGHT), Image.Resampling.LANCZOS)

        draw = ImageDraw.Draw(img)

        # Try to load Chinese font, fallback to default
        font_paths = [
            # Docker / Ubuntu (fonts-noto-cjk package)
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            # macOS
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            # Windows
            "C:\\Windows\\Fonts\\msyh.ttc",
            "C:\\Windows\\Fonts\\simhei.ttf",
        ]

        def load_font(size: int) -> ImageFont.FreeTypeFont:
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        return ImageFont.truetype(font_path, size)
                    except Exception:
                        continue
            # Fallback to default
            return ImageFont.load_default()

        # Fonts
        main_font = load_font(72)
        sub_font = load_font(64)
        badge_font = load_font(36)

        # Colors
        yellow = (255, 255, 0)
        white = (255, 255, 255)
        blue = (0, 120, 200)
        black_outline = (0, 0, 0)

        def draw_text_with_outline(
            draw: ImageDraw.Draw,
            position: Tuple[int, int],
            text: str,
            font: ImageFont.FreeTypeFont,
            fill_color: Tuple[int, int, int],
            outline_color: Tuple[int, int, int] = black_outline,
            outline_width: int = 3,
        ):
            """Draw text with outline for better visibility."""
            x, y = position
            # Draw outline
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
            # Draw main text
            draw.text(position, text, font=font, fill=fill_color)

        # Draw main title (yellow, center-bottom area)
        main_bbox = draw.textbbox((0, 0), main_title, font=main_font)
        main_width = main_bbox[2] - main_bbox[0]
        main_x = (YOUTUBE_WIDTH - main_width) // 2
        main_y = YOUTUBE_HEIGHT - 220

        draw_text_with_outline(draw, (main_x, main_y), main_title, main_font, yellow, outline_width=4)

        # Draw blue bar at bottom
        bar_height = 90
        bar_y = YOUTUBE_HEIGHT - bar_height
        draw.rectangle([(0, bar_y), (YOUTUBE_WIDTH, YOUTUBE_HEIGHT)], fill=blue)

        # Draw sub title (white on blue bar)
        sub_bbox = draw.textbbox((0, 0), sub_title, font=sub_font)
        sub_width = sub_bbox[2] - sub_bbox[0]
        sub_x = (YOUTUBE_WIDTH - sub_width) // 2
        sub_y = bar_y + (bar_height - (sub_bbox[3] - sub_bbox[1])) // 2 - 5

        draw.text((sub_x, sub_y), sub_title, font=sub_font, fill=white)

        # Draw corner badge (top-left)
        badge_padding = 10
        badge_bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        badge_width = badge_bbox[2] - badge_bbox[0] + badge_padding * 2
        badge_height = badge_bbox[3] - badge_bbox[1] + badge_padding * 2

        # Badge background (yellow)
        draw.rectangle([(20, 20), (20 + badge_width, 20 + badge_height)], fill=yellow)
        # Badge text (black)
        draw.text((20 + badge_padding, 20 + badge_padding - 5), badge_text, font=badge_font, fill=(0, 0, 0))

        # Save to bytes
        output = io.BytesIO()
        img.save(output, format="PNG", quality=95)
        return output.getvalue()

    async def generate_thumbnail(
        self,
        prompt: str,
        output_path: Path,
    ) -> Optional[Path]:
        """Generate thumbnail image (legacy method for backward compatibility).

        Args:
            prompt: Image generation prompt
            output_path: Where to save the image

        Returns:
            Path to generated image or None if failed
        """
        if not self.enabled:
            logger.warning("Thumbnail generation is disabled. Set IMAGE_MODEL env var to enable.")
            return None

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        image_bytes = await self.generate_base_image(prompt)
        if not image_bytes:
            return None

        with open(output_path, "wb") as f:
            f.write(image_bytes)

        logger.info(f"Generated thumbnail using {self.image_model}: {output_path}")
        return output_path

    async def generate_for_timeline(
        self,
        title: str,
        subtitles: list[str],
        output_dir: Path,
        filename: Optional[str] = None,
    ) -> Optional[Path]:
        """Generate a YouTube-style thumbnail for a timeline.

        Args:
            title: Video title
            subtitles: List of English subtitles
            output_dir: Directory to save thumbnail
            filename: Optional filename (default: thumbnail_<hash>.png)

        Returns:
            Path to generated thumbnail or None
        """
        if not self.enabled:
            logger.warning("Thumbnail generation is disabled.")
            return None

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: Generate clickbait Chinese titles
        logger.info("Generating clickbait titles...")
        main_title, sub_title = await self.generate_clickbait_title(title, subtitles)
        logger.info(f"Titles: {main_title} / {sub_title}")

        # Step 2: Generate image prompt
        logger.info("Generating image prompt...")
        image_prompt = await self.generate_image_prompt(title, subtitles)
        logger.info(f"Image prompt: {image_prompt[:100]}...")

        # Step 3: Generate base image
        logger.info("Generating base image...")
        base_image = await self.generate_base_image(image_prompt)
        if not base_image:
            logger.error("Failed to generate base image")
            return None

        # Step 4: Add text overlays
        logger.info("Adding text overlays...")
        final_image = self.add_text_overlay(base_image, main_title, sub_title)

        # Save final image
        if not filename:
            content_hash = hashlib.md5(f"{title}{main_title}".encode()).hexdigest()[:8]
            filename = f"thumbnail_{content_hash}.png"

        output_path = output_dir / filename
        with open(output_path, "wb") as f:
            f.write(final_image)

        logger.info(f"Generated YouTube-style thumbnail: {output_path}")
        return output_path
