"""Thumbnail generation worker for YouTube-style video covers.

Uses video screenshots (not AI-generated images) for authenticity.
"""

import hashlib
import httpx
import io
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List
from loguru import logger

from app.config import settings

# YouTube thumbnail dimensions
YOUTUBE_WIDTH = 1280
YOUTUBE_HEIGHT = 720


class ThumbnailWorker:
    """Worker for generating YouTube-style video thumbnails from video frames."""

    def __init__(self):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.enabled = bool(self.api_key)

    async def analyze_emotional_moments(
        self,
        subtitles: List[dict],
    ) -> Tuple[float, str]:
        """Analyze subtitles to find the most dramatic/emotional moment.

        Args:
            subtitles: List of subtitle dicts with 'start', 'end', 'en' keys

        Returns:
            Tuple of (timestamp, reason) for the most eye-catching moment
        """
        # Format subtitles for analysis
        subtitle_text = "\n".join([
            f"[{s.get('start', 0):.1f}s] {s.get('en', s.get('text', ''))}"
            for s in subtitles[:50]  # Analyze first 50 segments
        ])

        system_prompt = """你是一个视频封面设计专家。分析视频台词，找出最适合做封面的那一刻。

寻找以下类型的时刻：
- 冲突、对抗、争论
- 震惊、惊讶的反应
- 重要宣布、声明
- 情绪激动的表达
- 有争议性的言论

返回JSON格式：
{"timestamp": 秒数, "reason": "为什么选这个时刻"}

只输出JSON，不要其他内容。"""

        user_prompt = f"""分析以下台词，找出最适合做YouTube封面的时刻：

{subtitle_text}

选择最博眼球、最有冲击力的那一刻："""

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
                        "max_tokens": 150,
                        "temperature": 0.7,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"].strip()

                # Parse JSON response
                import json
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                result = json.loads(content)
                timestamp = float(result.get("timestamp", 10))
                reason = result.get("reason", "")

                logger.info(f"Selected moment at {timestamp}s: {reason}")
                return timestamp, reason

        except Exception as e:
            logger.error(f"Failed to analyze emotional moments: {e}")
            # Default to 10 seconds into the video
            return 10.0, "Default selection"

    async def generate_clickbait_title(
        self,
        title: str,
        subtitles: List[dict],
    ) -> Tuple[str, str]:
        """Generate clickbait Chinese titles for thumbnail.

        Args:
            title: Video title
            subtitles: List of subtitle dicts

        Returns:
            Tuple of (main_title, sub_title) in Chinese
        """
        content_sample = " ".join([
            s.get('en', s.get('text', '')) for s in subtitles[:15]
        ])[:800]

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
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]

                titles = json.loads(content)
                return titles.get("main", "精彩內容"), titles.get("sub", "不容錯過")

        except Exception as e:
            logger.error(f"Failed to generate clickbait title: {e}")
            return "精彩內容", "不容錯過"

    def extract_frame(
        self,
        video_path: Path,
        timestamp: float,
        output_path: Path,
    ) -> Optional[Path]:
        """Extract a frame from video at given timestamp.

        Args:
            video_path: Path to video file
            timestamp: Time in seconds
            output_path: Where to save the frame

        Returns:
            Path to extracted frame or None if failed
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",  # High quality JPEG
            "-y",  # Overwrite
            str(output_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return None

            if output_path.exists():
                logger.info(f"Extracted frame at {timestamp}s: {output_path}")
                return output_path
            else:
                logger.error("Frame extraction completed but file not found")
                return None

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg timeout")
            return None
        except Exception as e:
            logger.exception(f"Failed to extract frame: {e}")
            return None

    def add_text_overlay(
        self,
        image_path: Path,
        main_title: str,
        sub_title: str,
        badge_text: str = "中英對照",
    ) -> bytes:
        """Add text overlays to the thumbnail image.

        Args:
            image_path: Path to base image
            main_title: Main title (yellow text)
            sub_title: Sub title (white text on blue bar)
            badge_text: Corner badge text

        Returns:
            Final image bytes
        """
        from PIL import Image, ImageDraw, ImageFont, ImageEnhance
        import os

        # Load and resize image
        img = Image.open(image_path)
        img = img.resize((YOUTUBE_WIDTH, YOUTUBE_HEIGHT), Image.Resampling.LANCZOS)

        # Slightly increase contrast for more dramatic look
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.1)

        draw = ImageDraw.Draw(img)

        # Try to load Chinese font
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
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
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

        draw.rectangle([(20, 20), (20 + badge_width, 20 + badge_height)], fill=yellow)
        draw.text((20 + badge_padding, 20 + badge_padding - 5), badge_text, font=badge_font, fill=(0, 0, 0))

        # Save to bytes
        output = io.BytesIO()
        img.save(output, format="PNG", quality=95)
        return output.getvalue()

    async def generate_for_timeline(
        self,
        title: str,
        subtitles: List[dict],
        video_path: Path,
        output_dir: Path,
        filename: Optional[str] = None,
    ) -> Optional[Path]:
        """Generate a YouTube-style thumbnail for a timeline.

        Args:
            title: Video title
            subtitles: List of subtitle dicts with 'start', 'end', 'en' keys
            video_path: Path to source video
            output_dir: Directory to save thumbnail
            filename: Optional filename

        Returns:
            Path to generated thumbnail or None
        """
        if not self.enabled:
            logger.warning("Thumbnail generation disabled (no LLM API key)")
            return None

        video_path = Path(video_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not video_path.exists():
            logger.error(f"Video file not found: {video_path}")
            return None

        # Step 1: Analyze subtitles to find best moment
        logger.info("Analyzing emotional moments...")
        timestamp, reason = await self.analyze_emotional_moments(subtitles)

        # Step 2: Generate clickbait titles
        logger.info("Generating clickbait titles...")
        main_title, sub_title = await self.generate_clickbait_title(title, subtitles)
        logger.info(f"Titles: {main_title} / {sub_title}")

        # Step 3: Extract frame from video
        logger.info(f"Extracting frame at {timestamp}s...")
        frame_path = output_dir / "temp_frame.jpg"
        frame_result = self.extract_frame(video_path, timestamp, frame_path)

        if not frame_result:
            # Fallback: try at 10 seconds
            logger.warning("Frame extraction failed, trying fallback at 10s...")
            frame_result = self.extract_frame(video_path, 10.0, frame_path)

        if not frame_result:
            logger.error("Failed to extract frame from video")
            return None

        # Step 4: Add text overlays
        logger.info("Adding text overlays...")
        final_image = self.add_text_overlay(frame_path, main_title, sub_title)

        # Clean up temp frame
        try:
            frame_path.unlink()
        except Exception:
            pass

        # Save final image
        if not filename:
            content_hash = hashlib.md5(f"{title}{main_title}{timestamp}".encode()).hexdigest()[:8]
            filename = f"thumbnail_{content_hash}.png"

        output_path = output_dir / filename
        with open(output_path, "wb") as f:
            f.write(final_image)

        logger.info(f"Generated thumbnail from video frame: {output_path}")
        return output_path
