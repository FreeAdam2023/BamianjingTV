"""Card renderer for video export - generates PNG images of word/entity cards.

Supports two rendering modes:
- Compact overlay cards (render_word_card, render_entity_card) for floating overlays
- Full detail panel cards (render_full_*) for WYSIWYG side panel export
"""

import base64
import hashlib
import io
import time
from pathlib import Path
from typing import Optional, Tuple, List
from urllib.parse import urlparse
from loguru import logger

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow not installed. Card rendering will not be available.")


# Image cache directory for downloaded images
IMAGE_CACHE_DIR = Path("data/cards/images")


# Domain-specific headers — Wikimedia requires bot UA; Pixabay wants browser UA
_WIKIMEDIA_HEADERS = {
    "User-Agent": "SceneMindBot/1.0 (https://github.com/FreeAdam2023/BamianjingTV; scenemind@proton.me) python-httpx/0.27",
}
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}
# Track last download time for throttling
_last_download_time: float = 0.0
_DOWNLOAD_INTERVAL = 0.5  # seconds between downloads (gentle rate)


def _headers_for_url(url: str) -> dict:
    """Pick headers based on the image host."""
    host = urlparse(url).hostname or ""
    if "wikimedia" in host or "wikipedia" in host:
        return _WIKIMEDIA_HEADERS
    return _BROWSER_HEADERS


def _download_image(url: str, throttle: bool = False) -> Optional[Image.Image]:
    """Download an image from URL with caching.

    Args:
        url: Image URL to download
        throttle: If True, wait between requests to avoid rate limits

    Returns:
        PIL Image or None on failure
    """
    if not url:
        return None

    # Check cache first
    url_hash = hashlib.md5(url.encode()).hexdigest()
    cache_path = IMAGE_CACHE_DIR / f"{url_hash}.png"

    if cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGBA")
        except Exception:
            pass

    # Throttle if requested (batch downloads)
    global _last_download_time
    if throttle:
        elapsed = time.monotonic() - _last_download_time
        if elapsed < _DOWNLOAD_INTERVAL:
            time.sleep(_DOWNLOAD_INTERVAL - elapsed)

    # Download image with domain-specific headers
    try:
        import httpx

        headers = _headers_for_url(url)
        with httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers=headers,
        ) as client:
            response = client.get(url)

            # Handle rate limiting with retry
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 5))
                logger.info(f"Rate limited, waiting {retry_after}s: {url}")
                time.sleep(retry_after)
                response = client.get(url)

            response.raise_for_status()
            img = Image.open(io.BytesIO(response.content)).convert("RGBA")

            # Cache it
            IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
            img.save(cache_path, "PNG")
            logger.debug(f"Cached image: {url} -> {cache_path}")
            _last_download_time = time.monotonic()
            return img
    except Exception as e:
        logger.warning(f"Failed to download image {url}: {e}")
        _last_download_time = time.monotonic()
        return None


def _extract_image_urls(card_data: Optional[dict], card_type: str) -> list[str]:
    """Extract image URLs from card data."""
    if not card_data:
        return []
    if card_type == "entity" and card_data.get("image_url"):
        return [card_data["image_url"]]
    if card_type == "word":
        return list(card_data.get("images", [])[:3])
    return []


def precache_card_images(card_data: Optional[dict], card_type: str) -> int:
    """Pre-download and cache images from card data.

    Called when a card is pinned so images are already local during export.
    Returns the number of images successfully cached.
    """
    urls = _extract_image_urls(card_data, card_type)
    cached = 0
    for url in urls:
        if _download_image(url, throttle=True) is not None:
            cached += 1
    if urls:
        logger.info(f"Pre-cached {cached}/{len(urls)} images for {card_type} card")
    return cached


def batch_precache_images(
    pinned_cards: list[dict],
) -> int:
    """Pre-download all images for a list of pinned cards before export.

    Throttles requests to avoid triggering rate limits. Cards whose images
    are already cached will be skipped (fast path via cache_path.exists()).
    """
    total = 0
    skipped = 0
    for card in pinned_cards:
        card_type = card.get("card_type", "")
        card_data = card.get("card_data")
        urls = _extract_image_urls(card_data, card_type)
        for url in urls:
            url_hash = hashlib.md5(url.encode()).hexdigest()
            cache_path = IMAGE_CACHE_DIR / f"{url_hash}.png"
            if cache_path.exists():
                skipped += 1
                continue
            if _download_image(url, throttle=True) is not None:
                total += 1
    logger.info(
        f"Batch pre-cache complete: {total} downloaded, {skipped} already cached"
    )
    return total


class CardRenderer:
    """Renderer for generating card images for video overlay."""

    # Card dimensions
    CARD_WIDTH = 400
    CARD_PADDING = 24
    CARD_RADIUS = 16

    # Colors (RGBA)
    BG_COLOR = (26, 39, 68, 230)  # #1a2744 with 90% opacity
    BG_SOLID = (26, 39, 68, 255)  # #1a2744 fully opaque (for full panel)
    TEXT_WHITE = (255, 255, 255, 255)
    TEXT_MUTED = (255, 255, 255, 153)  # 60% opacity
    TEXT_YELLOW = (250, 204, 21, 255)  # #facc15
    TEXT_BLUE = (147, 197, 253, 255)  # blue-300
    TEXT_PURPLE = (196, 181, 253, 255)  # purple-300
    TEXT_GREEN = (134, 239, 172, 255)  # green-300
    TEXT_RED = (252, 165, 165, 255)  # red-300
    TEXT_AMBER = (252, 211, 77, 255)  # amber-300
    DIVIDER_COLOR = (255, 255, 255, 26)  # 10% opacity

    # Entity type colors
    ENTITY_TYPE_COLORS = {
        "person": (59, 130, 246, 200),  # blue-500
        "place": (34, 197, 94, 200),  # green-500
        "organization": (168, 85, 247, 200),  # purple-500
        "event": (249, 115, 22, 200),  # orange-500
        "work": (236, 72, 153, 200),  # pink-500
        "concept": (6, 182, 212, 200),  # cyan-500
        "product": (234, 179, 8, 200),  # yellow-500
        "other": (107, 114, 128, 200),  # gray-500
    }

    # Idiom category colors
    IDIOM_CATEGORY_COLORS = {
        "idiom": (245, 158, 11, 128),  # amber-500 50%
        "phrasal_verb": (217, 119, 6, 128),  # amber-600 50%
        "slang": (249, 115, 22, 128),  # orange-500 50%
    }
    IDIOM_CATEGORY_LABELS = {
        "idiom": "Idiom",
        "phrasal_verb": "Phrasal Verb",
        "slang": "Slang",
    }

    # Source badge colors
    BADGE_BG = (255, 255, 255, 26)  # white/10

    def __init__(self, fonts_dir: Optional[Path] = None):
        """Initialize card renderer.

        Args:
            fonts_dir: Directory containing font files
        """
        if not PILLOW_AVAILABLE:
            raise RuntimeError("Pillow is required for card rendering")

        self.fonts_dir = fonts_dir or Path(__file__).parent / "fonts"

        # Load fonts (with fallbacks)
        self._load_fonts()

    @staticmethod
    def _find_font(candidates: list[str], size: int):
        """Try loading a font from a list of candidate paths."""
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
        return None

    def _load_fonts(self) -> None:
        """Load fonts with cross-platform fallbacks."""
        # English font candidates (macOS → Linux → generic)
        en_fonts = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]
        # Chinese font candidates (macOS → Linux → generic)
        zh_fonts = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Hiragino Sans GB.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]

        default = ImageFont.load_default()

        def _load(candidates, size):
            return self._find_font(candidates, size) or default

        # Primary fonts
        self.font_title = _load(en_fonts, 28)
        self.font_body = _load(en_fonts, 18)
        self.font_small = _load(en_fonts, 14)
        self.font_ipa = _load(en_fonts, 16)

        # Chinese fonts (fall back to English font if no CJK font found)
        zh_fallback = zh_fonts + en_fonts
        self.font_zh_title = _load(zh_fallback, 24)
        self.font_zh_body = _load(zh_fallback, 18)
        self.font_zh_small = _load(zh_fallback, 14)

        # Larger fonts for full panel cards
        self.font_panel_title = _load(en_fonts, 24)
        self.font_panel_body = _load(en_fonts, 16)
        self.font_panel_small = _load(en_fonts, 13)
        self.font_panel_zh_title = _load(zh_fallback, 22)
        self.font_panel_zh_body = _load(zh_fallback, 16)
        self.font_panel_zh_small = _load(zh_fallback, 13)

        # Log what was found
        en_found = self.font_title != default
        zh_found = self.font_zh_title != default
        if en_found and zh_found:
            logger.info("Fonts loaded: EN=%s, ZH=%s",
                        getattr(self.font_title, 'path', '?'),
                        getattr(self.font_zh_title, 'path', '?'))
        elif en_found:
            logger.warning("Chinese fonts not found — CJK text may render poorly")
        else:
            logger.warning("No system fonts found, using Pillow default bitmap font")

    def _draw_rounded_rect(
        self,
        draw: ImageDraw.ImageDraw,
        xy: Tuple[int, int, int, int],
        radius: int,
        fill: Tuple[int, int, int, int],
    ) -> None:
        """Draw a rounded rectangle."""
        x1, y1, x2, y2 = xy
        draw.rounded_rectangle(xy, radius=radius, fill=fill)

    def _wrap_text(
        self,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_width: int,
    ) -> List[str]:
        """Wrap text to fit within max_width."""
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = font.getbbox(test_line)
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return lines if lines else [text]

    def _draw_section_header(
        self,
        draw: ImageDraw.ImageDraw,
        y: int,
        label: str,
        padding: int,
        content_width: int,
    ) -> int:
        """Draw a section header with label and divider line.

        Returns:
            New y position after header
        """
        draw.text(
            (padding, y),
            label.upper(),
            font=self.font_panel_small,
            fill=self.TEXT_MUTED,
        )
        label_bbox = self.font_panel_small.getbbox(label.upper())
        line_x = padding + label_bbox[2] - label_bbox[0] + 12
        draw.line(
            [(line_x, y + 8), (padding + content_width, y + 8)],
            fill=self.DIVIDER_COLOR,
            width=1,
        )
        return y + 24

    def _paste_image_header(
        self,
        img: Image.Image,
        header_img: Image.Image,
        panel_width: int,
        header_height: int,
    ) -> None:
        """Paste and scale an image into the header area with gradient overlay."""
        # Scale image to fill header width, maintaining aspect ratio
        aspect = header_img.width / header_img.height
        if aspect >= panel_width / header_height:
            # Image is wider - fit to height
            new_h = header_height
            new_w = int(header_height * aspect)
        else:
            # Image is taller - fit to width
            new_w = panel_width
            new_h = int(panel_width / aspect)

        header_img = header_img.resize((new_w, new_h), Image.LANCZOS)
        # Center crop to panel_width x header_height
        x_off = (new_w - panel_width) // 2
        y_off = (new_h - header_height) // 2
        header_img = header_img.crop((x_off, y_off, x_off + panel_width, y_off + header_height))

        # Paste image
        img.paste(header_img, (0, 0))

        # Draw gradient overlay (bottom to top fade from dark)
        gradient = Image.new("RGBA", (panel_width, header_height), (0, 0, 0, 0))
        gradient_draw = ImageDraw.Draw(gradient)
        for gy in range(header_height):
            # Bottom 80% of image gets increasing darkness
            progress = gy / header_height
            if progress > 0.2:
                alpha = int(204 * ((progress - 0.2) / 0.8))  # 0 to 204 (~80%)
            else:
                alpha = 0
            gradient_draw.line(
                [(0, gy), (panel_width, gy)],
                fill=(0, 0, 0, alpha),
            )
        img.alpha_composite(gradient)

    # ========== Compact overlay card renderers (existing) ==========

    def render_word_card(
        self,
        word: str,
        ipa: Optional[str] = None,
        cefr_level: Optional[str] = None,
        senses: Optional[List[dict]] = None,
        output_path: Optional[Path] = None,
    ) -> Image.Image:
        """Render a compact word card as PNG for floating overlay."""
        content_width = self.CARD_WIDTH - 2 * self.CARD_PADDING
        y = self.CARD_PADDING

        # Estimate height
        height = self.CARD_PADDING
        height += 36  # Word title
        if ipa:
            height += 24
        if cefr_level:
            height += 28
        height += 16

        if senses:
            for sense in senses[:2]:
                height += 28
                if sense.get("definition_zh"):
                    lines = self._wrap_text(sense["definition_zh"], self.font_zh_body, content_width - 20)
                    height += len(lines) * 24
                if sense.get("definition"):
                    lines = self._wrap_text(sense["definition"], self.font_body, content_width - 20)
                    height += len(lines) * 22
                if sense.get("examples") and sense["examples"]:
                    height += 40
                height += 16

        height += self.CARD_PADDING
        height = max(height, 200)

        img = Image.new("RGBA", (self.CARD_WIDTH, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        self._draw_rounded_rect(draw, (0, 0, self.CARD_WIDTH, height), self.CARD_RADIUS, self.BG_COLOR)

        draw.text((self.CARD_PADDING, y), word, font=self.font_title, fill=self.TEXT_WHITE)
        y += 36

        if ipa:
            draw.text((self.CARD_PADDING, y), ipa, font=self.font_ipa, fill=self.TEXT_BLUE)
            y += 24

        if cefr_level:
            badge_text = cefr_level.upper()
            badge_bbox = self.font_small.getbbox(badge_text)
            badge_width = badge_bbox[2] - badge_bbox[0] + 16
            badge_height = 22
            self._draw_rounded_rect(
                draw,
                (self.CARD_PADDING, y, self.CARD_PADDING + badge_width, y + badge_height),
                6, (168, 85, 247, 77),
            )
            draw.text((self.CARD_PADDING + 8, y + 3), badge_text, font=self.font_small, fill=self.TEXT_PURPLE)
            y += 28

        y += 8

        if senses:
            for i, sense in enumerate(senses[:2]):
                pos = sense.get("part_of_speech", "")
                if pos:
                    draw.text((self.CARD_PADDING, y), pos.upper(), font=self.font_small, fill=self.TEXT_MUTED)
                    pos_bbox = self.font_small.getbbox(pos.upper())
                    line_x = self.CARD_PADDING + pos_bbox[2] - pos_bbox[0] + 12
                    draw.line(
                        [(line_x, y + 8), (self.CARD_WIDTH - self.CARD_PADDING, y + 8)],
                        fill=self.DIVIDER_COLOR, width=1,
                    )
                    y += 24

                if sense.get("definition_zh"):
                    def_text = f"{i + 1}. {sense['definition_zh']}"
                    lines = self._wrap_text(def_text, self.font_zh_body, content_width - 20)
                    for line in lines:
                        draw.text((self.CARD_PADDING + 8, y), line, font=self.font_zh_body, fill=self.TEXT_WHITE)
                        y += 24

                if sense.get("definition") and sense["definition"] != sense.get("definition_zh"):
                    lines = self._wrap_text(sense["definition"], self.font_body, content_width - 30)
                    for line in lines[:2]:
                        draw.text((self.CARD_PADDING + 16, y), line, font=self.font_body, fill=self.TEXT_MUTED)
                        y += 22

                examples = sense.get("examples", [])
                examples_zh = sense.get("examples_zh", [])
                if examples:
                    example = examples[0]
                    draw.rectangle(
                        (self.CARD_PADDING + 12, y + 2, self.CARD_PADDING + 14, y + 36),
                        fill=self.DIVIDER_COLOR,
                    )
                    ex_lines = self._wrap_text(f'"{example}"', self.font_small, content_width - 40)
                    draw.text(
                        (self.CARD_PADDING + 20, y),
                        ex_lines[0] if ex_lines else "",
                        font=self.font_small, fill=self.TEXT_MUTED,
                    )
                    y += 18
                    if examples_zh and examples_zh[0]:
                        draw.text(
                            (self.CARD_PADDING + 20, y),
                            examples_zh[0][:40] + ("..." if len(examples_zh[0]) > 40 else ""),
                            font=self.font_zh_small, fill=self.TEXT_YELLOW,
                        )
                        y += 18

                y += 12

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            logger.debug(f"Saved word card: {output_path}")

        return img

    def render_entity_card(
        self,
        name: str,
        entity_type: str,
        description: Optional[str] = None,
        name_zh: Optional[str] = None,
        description_zh: Optional[str] = None,
        image_url: Optional[str] = None,
        output_path: Optional[Path] = None,
    ) -> Image.Image:
        """Render a compact entity card as PNG for floating overlay."""
        content_width = self.CARD_WIDTH - 2 * self.CARD_PADDING

        height = self.CARD_PADDING
        height += 32  # Type badge
        height += 36  # Name
        if name_zh and name_zh != name:
            height += 24
        height += 12

        if description:
            lines = self._wrap_text(description, self.font_body, content_width)
            height += min(len(lines), 3) * 22
            height += 8

        if description_zh:
            lines = self._wrap_text(description_zh, self.font_zh_body, content_width)
            height += min(len(lines), 2) * 24

        height += self.CARD_PADDING
        height = max(height, 180)

        img = Image.new("RGBA", (self.CARD_WIDTH, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        self._draw_rounded_rect(draw, (0, 0, self.CARD_WIDTH, height), self.CARD_RADIUS, self.BG_COLOR)

        y = self.CARD_PADDING

        type_color = self.ENTITY_TYPE_COLORS.get(entity_type.lower(), self.ENTITY_TYPE_COLORS["other"])
        badge_text = entity_type.upper()
        badge_bbox = self.font_small.getbbox(badge_text)
        badge_width = badge_bbox[2] - badge_bbox[0] + 16
        badge_height = 22
        self._draw_rounded_rect(
            draw,
            (self.CARD_PADDING, y, self.CARD_PADDING + badge_width, y + badge_height),
            6, type_color,
        )
        draw.text((self.CARD_PADDING + 8, y + 3), badge_text, font=self.font_small, fill=self.TEXT_WHITE)
        y += 32

        draw.text((self.CARD_PADDING, y), name, font=self.font_title, fill=self.TEXT_WHITE)
        y += 36

        if name_zh and name_zh != name:
            draw.text((self.CARD_PADDING, y), name_zh, font=self.font_zh_body, fill=self.TEXT_YELLOW)
            y += 24

        y += 8

        if description:
            lines = self._wrap_text(description, self.font_body, content_width)
            for line in lines[:3]:
                draw.text((self.CARD_PADDING, y), line, font=self.font_body, fill=self.TEXT_MUTED)
                y += 22
            y += 4

        if description_zh:
            lines = self._wrap_text(description_zh, self.font_zh_body, content_width)
            for line in lines[:2]:
                draw.text((self.CARD_PADDING, y), line, font=self.font_zh_body, fill=self.TEXT_MUTED)
                y += 24

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            logger.debug(f"Saved entity card: {output_path}")

        return img

    # ========== Full detail panel renderers (WYSIWYG export) ==========

    def render_full_entity_card(
        self,
        card_data: dict,
        panel_width: int,
        panel_height: int,
        output_path: Optional[Path] = None,
    ) -> Image.Image:
        """Render a full-detail entity card matching CardSidePanel.tsx.

        Includes: image header, type badge, name, Chinese name,
        description (EN + ZH), source badges (Wikipedia/Wikidata).
        """
        padding = 20
        content_width = panel_width - 2 * padding

        name = card_data.get("name", "")
        entity_type = card_data.get("entity_type", "other")
        description = card_data.get("description")
        image_url = card_data.get("image_url")
        wikipedia_url = card_data.get("wikipedia_url")
        wikidata_url = card_data.get("wikidata_url")

        localizations = card_data.get("localizations", {})
        zh_loc = localizations.get("zh", {})
        name_zh = zh_loc.get("name")
        description_zh = zh_loc.get("description")

        # Create panel image
        img = Image.new("RGBA", (panel_width, panel_height), self.BG_SOLID)
        draw = ImageDraw.Draw(img)

        # Image header (~40% of panel height)
        header_height = int(panel_height * 0.3)
        header_img = _download_image(image_url)
        if header_img:
            self._paste_image_header(img, header_img, panel_width, header_height)
            draw = ImageDraw.Draw(img)  # Refresh draw after paste
        else:
            # No image: subtle gradient header
            for gy in range(min(64, header_height)):
                alpha = int(26 * (1 - gy / 64))  # Subtle white gradient
                draw.line([(0, gy), (panel_width, gy)], fill=(255, 255, 255, alpha))
            header_height = 64

        # Entity type badge (top-left of header)
        type_color = self.ENTITY_TYPE_COLORS.get(entity_type.lower(), self.ENTITY_TYPE_COLORS["other"])
        badge_text = entity_type.upper()
        badge_bbox = self.font_panel_small.getbbox(badge_text)
        badge_w = badge_bbox[2] - badge_bbox[0] + 16
        self._draw_rounded_rect(
            draw, (padding, 12, padding + badge_w, 12 + 22), 6, type_color,
        )
        draw.text((padding + 8, 12 + 3), badge_text, font=self.font_panel_small, fill=self.TEXT_WHITE)

        # Content starts below header
        y = header_height + 16

        # Name
        name_lines = self._wrap_text(name, self.font_panel_title, content_width)
        for line in name_lines[:2]:
            draw.text((padding, y), line, font=self.font_panel_title, fill=self.TEXT_WHITE)
            y += 30
        y += 2

        # Chinese name
        if name_zh and name_zh != name:
            draw.text((padding, y), name_zh, font=self.font_panel_zh_body, fill=self.TEXT_YELLOW)
            y += 22

        y += 12

        # English description
        if description:
            lines = self._wrap_text(description, self.font_panel_body, content_width)
            for line in lines[:5]:
                if y + 20 > panel_height - 50:
                    draw.text((padding, y), line[:40] + "...", font=self.font_panel_body, fill=self.TEXT_MUTED)
                    y += 20
                    break
                draw.text((padding, y), line, font=self.font_panel_body, fill=self.TEXT_MUTED)
                y += 20
            y += 6

        # Chinese description
        if description_zh and description_zh != description:
            lines = self._wrap_text(description_zh, self.font_panel_zh_body, content_width)
            for line in lines[:4]:
                if y + 22 > panel_height - 50:
                    break
                draw.text((padding, y), line, font=self.font_panel_zh_body, fill=self.TEXT_MUTED)
                y += 22
            y += 8

        # Source badges at bottom
        badge_y = max(y + 12, panel_height - 40)
        badge_x = padding
        for label, url in [("Wikipedia", wikipedia_url), ("Wikidata", wikidata_url)]:
            if url and badge_y < panel_height - 10:
                text_bbox = self.font_panel_small.getbbox(label)
                text_w = text_bbox[2] - text_bbox[0] + 16
                self._draw_rounded_rect(
                    draw,
                    (badge_x, badge_y, badge_x + text_w, badge_y + 24),
                    6, self.BADGE_BG,
                )
                draw.text((badge_x + 8, badge_y + 4), label, font=self.font_panel_small, fill=self.TEXT_MUTED)
                badge_x += text_w + 8

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            logger.debug(f"Saved full entity card: {output_path}")

        return img

    def render_full_word_card(
        self,
        card_data: dict,
        panel_width: int,
        panel_height: int,
        output_path: Optional[Path] = None,
    ) -> Image.Image:
        """Render a full-detail word card matching CardSidePanel.tsx.

        Includes: image header, word + lemma + CEFR badge, IPA,
        senses grouped by POS (up to 3), examples with bilingual translations,
        synonyms/antonyms tags.
        """
        padding = 20
        content_width = panel_width - 2 * padding

        word = card_data.get("word", "")
        lemma = card_data.get("lemma", word)
        cefr_level = card_data.get("cefr_level")
        images = card_data.get("images", [])
        senses = card_data.get("senses", [])

        pronunciations = card_data.get("pronunciations", [])
        ipa = None
        for p in pronunciations:
            if p.get("region") == "us" or not ipa:
                ipa = p.get("ipa")

        # Create panel image
        img = Image.new("RGBA", (panel_width, panel_height), self.BG_SOLID)
        draw = ImageDraw.Draw(img)

        # Image header
        header_height = 0
        if images:
            header_img = _download_image(images[0])
            if header_img:
                header_height = int(panel_height * 0.25)
                self._paste_image_header(img, header_img, panel_width, header_height)
                draw = ImageDraw.Draw(img)

        y = max(header_height - 50, 16) if header_height > 0 else 16

        # Word title + lemma
        draw.text((padding, y), word, font=self.font_panel_title, fill=self.TEXT_WHITE)
        word_bbox = self.font_panel_title.getbbox(word)
        word_w = word_bbox[2] - word_bbox[0]
        if lemma != word:
            draw.text(
                (padding + word_w + 10, y + 6),
                f"({lemma})",
                font=self.font_panel_small,
                fill=self.TEXT_MUTED,
            )
        y += 32

        # IPA pronunciation
        if ipa:
            draw.text((padding, y), ipa, font=self.font_panel_body, fill=self.TEXT_BLUE)
            y += 22

        # CEFR level badge
        if cefr_level:
            badge_text = cefr_level.upper()
            badge_bbox = self.font_panel_small.getbbox(badge_text)
            badge_w = badge_bbox[2] - badge_bbox[0] + 16
            self._draw_rounded_rect(
                draw,
                (padding, y, padding + badge_w, y + 22),
                6, (168, 85, 247, 77),
            )
            draw.text((padding + 8, y + 3), badge_text, font=self.font_panel_small, fill=self.TEXT_PURPLE)
            y += 28

        # Divider
        y += 4
        draw.line([(padding, y), (padding + content_width, y)], fill=self.DIVIDER_COLOR, width=1)
        y += 12

        # Group senses by POS
        senses_by_pos: dict = {}
        for sense in senses:
            pos = sense.get("part_of_speech", "other")
            if pos not in senses_by_pos:
                senses_by_pos[pos] = []
            senses_by_pos[pos].append(sense)

        # Render senses
        for pos, pos_senses in list(senses_by_pos.items()):
            if y + 30 > panel_height - 20:
                break

            # POS header with divider
            y = self._draw_section_header(draw, y, pos, padding, content_width)

            for idx, sense in enumerate(pos_senses[:3]):
                if y + 20 > panel_height - 20:
                    break

                # Chinese definition (primary)
                if sense.get("definition_zh"):
                    def_text = f"{idx + 1}. {sense['definition_zh']}"
                    lines = self._wrap_text(def_text, self.font_panel_zh_body, content_width - 16)
                    for line in lines[:2]:
                        if y + 20 > panel_height - 20:
                            break
                        draw.text((padding + 8, y), line, font=self.font_panel_zh_body, fill=self.TEXT_WHITE)
                        y += 20

                # English definition
                if sense.get("definition") and sense["definition"] != sense.get("definition_zh"):
                    lines = self._wrap_text(sense["definition"], self.font_panel_body, content_width - 28)
                    for line in lines[:2]:
                        if y + 18 > panel_height - 20:
                            break
                        draw.text((padding + 20, y), line, font=self.font_panel_body, fill=self.TEXT_MUTED)
                        y += 18

                # Example with bilingual translation
                examples = sense.get("examples", [])
                examples_zh = sense.get("examples_zh", [])
                if examples and y + 36 < panel_height - 20:
                    # Quote bar
                    draw.rectangle(
                        (padding + 16, y + 2, padding + 18, y + 32),
                        fill=self.DIVIDER_COLOR,
                    )
                    # English example
                    ex_lines = self._wrap_text(f'"{examples[0]}"', self.font_panel_small, content_width - 40)
                    draw.text((padding + 24, y), ex_lines[0], font=self.font_panel_small, fill=self.TEXT_MUTED)
                    y += 16
                    # Chinese translation
                    if examples_zh and examples_zh[0]:
                        zh_text = examples_zh[0][:50] + ("..." if len(examples_zh[0]) > 50 else "")
                        draw.text((padding + 24, y), zh_text, font=self.font_panel_zh_small, fill=self.TEXT_YELLOW)
                        y += 16
                    y += 4

                # Synonyms / Antonyms tags
                synonyms = sense.get("synonyms", [])
                antonyms = sense.get("antonyms", [])
                if (synonyms or antonyms) and y + 20 < panel_height - 20:
                    tag_x = padding + 16
                    if synonyms:
                        draw.text((tag_x, y + 2), "~", font=self.font_panel_small, fill=self.TEXT_GREEN)
                        tag_x += 14
                        for syn in synonyms[:3]:
                            syn_bbox = self.font_panel_small.getbbox(syn)
                            syn_w = syn_bbox[2] - syn_bbox[0] + 12
                            if tag_x + syn_w > padding + content_width:
                                break
                            self._draw_rounded_rect(
                                draw, (tag_x, y, tag_x + syn_w, y + 18),
                                4, (34, 197, 94, 40),
                            )
                            draw.text((tag_x + 6, y + 1), syn, font=self.font_panel_small, fill=self.TEXT_GREEN)
                            tag_x += syn_w + 6
                    if antonyms:
                        draw.text((tag_x, y + 2), "!=", font=self.font_panel_small, fill=self.TEXT_RED)
                        tag_x += 20
                        for ant in antonyms[:2]:
                            ant_bbox = self.font_panel_small.getbbox(ant)
                            ant_w = ant_bbox[2] - ant_bbox[0] + 12
                            if tag_x + ant_w > padding + content_width:
                                break
                            self._draw_rounded_rect(
                                draw, (tag_x, y, tag_x + ant_w, y + 18),
                                4, (239, 68, 68, 40),
                            )
                            draw.text((tag_x + 6, y + 1), ant, font=self.font_panel_small, fill=self.TEXT_RED)
                            tag_x += ant_w + 6
                    y += 24

                y += 8  # Spacing between senses

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            logger.debug(f"Saved full word card: {output_path}")

        return img

    def render_full_idiom_card(
        self,
        card_data: dict,
        panel_width: int,
        panel_height: int,
        output_path: Optional[Path] = None,
    ) -> Image.Image:
        """Render a full-detail idiom card matching CardSidePanel.tsx.

        Includes: amber gradient header, category badge, idiom text,
        sections: Meaning, Example, Origin, Usage Notes (all bilingual).
        """
        padding = 20
        content_width = panel_width - 2 * padding

        text = card_data.get("text", "")
        category = card_data.get("category", "idiom")
        meaning_original = card_data.get("meaning_original", "")
        meaning_localized = card_data.get("meaning_localized", "")
        example_original = card_data.get("example_original", "")
        example_localized = card_data.get("example_localized", "")
        origin_original = card_data.get("origin_original", "")
        origin_localized = card_data.get("origin_localized", "")
        usage_note_original = card_data.get("usage_note_original", "")
        usage_note_localized = card_data.get("usage_note_localized", "")

        # Create panel image
        img = Image.new("RGBA", (panel_width, panel_height), self.BG_SOLID)
        draw = ImageDraw.Draw(img)

        # Amber gradient header
        header_height = 64
        for gy in range(header_height):
            progress = gy / header_height
            # From amber-900/30 to amber-800/20
            r = int(120 + (140 - 120) * progress)
            g = int(53 + (60 - 53) * progress)
            b = int(15 + (20 - 15) * progress)
            alpha = int(77 - 26 * progress)  # 30% to 20%
            draw.line([(0, gy), (panel_width, gy)], fill=(r, g, b, alpha))

        # Category badge
        cat_color = self.IDIOM_CATEGORY_COLORS.get(category, self.IDIOM_CATEGORY_COLORS["idiom"])
        cat_label = self.IDIOM_CATEGORY_LABELS.get(category, category)
        cat_bbox = self.font_panel_small.getbbox(cat_label)
        cat_w = cat_bbox[2] - cat_bbox[0] + 16
        self._draw_rounded_rect(
            draw, (padding, 12, padding + cat_w, 12 + 22), 6, cat_color,
        )
        draw.text((padding + 8, 12 + 3), cat_label, font=self.font_panel_small, fill=self.TEXT_WHITE)

        y = header_height + 16

        # Idiom text in amber
        text_lines = self._wrap_text(text, self.font_panel_title, content_width)
        for line in text_lines[:2]:
            draw.text((padding, y), line, font=self.font_panel_title, fill=self.TEXT_AMBER)
            y += 30
        y += 12

        # Sections: Meaning, Example, Origin, Usage Notes
        sections = [
            ("Meaning", meaning_original, meaning_localized),
            ("Example", example_original, example_localized),
            ("Origin", origin_original, origin_localized),
            ("Usage Notes", usage_note_original, usage_note_localized),
        ]

        for section_label, en_text, zh_text in sections:
            if not en_text and not zh_text:
                continue
            if y + 30 > panel_height - 20:
                break

            y = self._draw_section_header(draw, y, section_label, padding, content_width)

            # For Example section, add quote bar styling
            is_example = section_label == "Example"

            if en_text:
                if is_example:
                    # Quote bar
                    bar_top = y
                    draw.text((padding + 16, y), f'"{en_text}"'[:80], font=self.font_panel_body, fill=self.TEXT_MUTED)
                    y += 20
                    if zh_text:
                        draw.text((padding + 16, y), zh_text[:60], font=self.font_panel_zh_body, fill=self.TEXT_YELLOW)
                        y += 20
                    # Draw the bar
                    draw.rectangle(
                        (padding + 8, bar_top, padding + 10, y - 4),
                        fill=(245, 158, 11, 77),  # amber-500/30
                    )
                else:
                    lines = self._wrap_text(en_text, self.font_panel_body, content_width)
                    for line in lines[:3]:
                        if y + 18 > panel_height - 20:
                            break
                        draw.text((padding, y), line, font=self.font_panel_body, fill=self.TEXT_MUTED)
                        y += 18

                    if zh_text:
                        y += 4
                        lines = self._wrap_text(zh_text, self.font_panel_zh_body, content_width)
                        for line in lines[:2]:
                            if y + 20 > panel_height - 20:
                                break
                            draw.text((padding, y), line, font=self.font_panel_zh_body, fill=self.TEXT_YELLOW)
                            y += 20

            elif zh_text:
                lines = self._wrap_text(zh_text, self.font_panel_zh_body, content_width)
                for line in lines[:2]:
                    if y + 20 > panel_height - 20:
                        break
                    draw.text((padding, y), line, font=self.font_panel_zh_body, fill=self.TEXT_YELLOW)
                    y += 20

            y += 12

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            logger.debug(f"Saved full idiom card: {output_path}")

        return img

    def render_full_insight_card(
        self,
        card_data: dict,
        panel_width: int,
        panel_height: int,
        output_path: Optional[Path] = None,
    ) -> Image.Image:
        """Render a full-detail insight card.

        Includes: purple gradient header, category badge, title,
        content text, related text reference, frame_data image.
        """
        padding = 20
        content_width = panel_width - 2 * padding

        title = card_data.get("title", "")
        content = card_data.get("content", "")
        category = card_data.get("category", "general")
        related_text = card_data.get("related_text")
        frame_data = card_data.get("frame_data")

        # Create panel image
        img = Image.new("RGBA", (panel_width, panel_height), self.BG_SOLID)
        draw = ImageDraw.Draw(img)

        # Purple gradient header
        header_height = 64
        for gy in range(header_height):
            progress = gy / header_height
            r = int(88 + (100 - 88) * progress)
            g = int(28 + (35 - 28) * progress)
            b = int(135 + (150 - 135) * progress)
            alpha = int(77 - 26 * progress)
            draw.line([(0, gy), (panel_width, gy)], fill=(r, g, b, alpha))

        # Category badge
        cat_bbox = self.font_panel_small.getbbox(category.upper())
        cat_w = cat_bbox[2] - cat_bbox[0] + 16
        self._draw_rounded_rect(
            draw, (padding, 12, padding + cat_w, 12 + 22), 6, (168, 85, 247, 128),
        )
        draw.text((padding + 8, 12 + 3), category.upper(), font=self.font_panel_small, fill=self.TEXT_WHITE)

        y = header_height + 16

        # Title
        title_lines = self._wrap_text(title, self.font_panel_title, content_width)
        for line in title_lines[:2]:
            draw.text((padding, y), line, font=self.font_panel_title, fill=self.TEXT_WHITE)
            y += 30
        y += 8

        # Related text
        if related_text:
            draw.rectangle(
                (padding + 4, y, padding + 6, y + 18),
                fill=self.DIVIDER_COLOR,
            )
            rt_text = f'"{related_text}"'[:70]
            draw.text((padding + 12, y), rt_text, font=self.font_panel_small, fill=self.TEXT_MUTED)
            y += 24

        # Frame data image
        if frame_data and y + 100 < panel_height - 60:
            try:
                frame_bytes = base64.b64decode(frame_data)
                frame_img = Image.open(io.BytesIO(frame_bytes)).convert("RGBA")
                # Scale to fit
                max_img_w = content_width
                max_img_h = min(150, panel_height - y - 80)
                aspect = frame_img.width / frame_img.height
                if frame_img.width / max_img_w > frame_img.height / max_img_h:
                    new_w = max_img_w
                    new_h = int(max_img_w / aspect)
                else:
                    new_h = max_img_h
                    new_w = int(max_img_h * aspect)
                frame_img = frame_img.resize((new_w, new_h), Image.LANCZOS)
                img.paste(frame_img, (padding, y))
                draw = ImageDraw.Draw(img)
                y += new_h + 12
            except Exception:
                pass

        # Content text
        if content:
            lines = self._wrap_text(content, self.font_panel_body, content_width)
            for line in lines:
                if y + 18 > panel_height - 10:
                    break
                draw.text((padding, y), line, font=self.font_panel_body, fill=self.TEXT_MUTED)
                y += 18

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            logger.debug(f"Saved full insight card: {output_path}")

        return img

    # ========== Dispatcher methods ==========

    def render_pinned_card(
        self,
        card_data: dict,
        card_type: str,
        output_path: Path,
    ) -> Path:
        """Render a compact pinned card based on its type and data.

        Args:
            card_data: Card data dictionary
            card_type: "word", "entity", "idiom", or "insight"
            output_path: Path to save the image

        Returns:
            Path to the saved image
        """
        if card_type == "word":
            word = card_data.get("word", "")
            pronunciations = card_data.get("pronunciations", [])
            ipa = None
            for p in pronunciations:
                if p.get("region") == "us" or not ipa:
                    ipa = p.get("ipa")

            self.render_word_card(
                word=word,
                ipa=ipa,
                cefr_level=card_data.get("cefr_level"),
                senses=card_data.get("senses", []),
                output_path=output_path,
            )
        elif card_type == "entity":
            localizations = card_data.get("localizations", {})
            zh_loc = localizations.get("zh", {})

            self.render_entity_card(
                name=card_data.get("name", ""),
                entity_type=card_data.get("entity_type", "other"),
                description=card_data.get("description"),
                name_zh=zh_loc.get("name"),
                description_zh=zh_loc.get("description"),
                output_path=output_path,
            )
        elif card_type == "idiom":
            # Render idiom as a compact card (reuse entity card style)
            text = card_data.get("text", "")
            meaning = card_data.get("meaning_original", "")
            meaning_zh = card_data.get("meaning_localized", "")
            category = card_data.get("category", "idiom")

            # Create compact idiom card using entity card as template
            content_width = self.CARD_WIDTH - 2 * self.CARD_PADDING
            height = self.CARD_PADDING + 32 + 36 + 12
            if meaning:
                lines = self._wrap_text(meaning, self.font_body, content_width)
                height += min(len(lines), 3) * 22 + 8
            if meaning_zh:
                lines = self._wrap_text(meaning_zh, self.font_zh_body, content_width)
                height += min(len(lines), 2) * 24
            height += self.CARD_PADDING
            height = max(height, 180)

            img = Image.new("RGBA", (self.CARD_WIDTH, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            self._draw_rounded_rect(draw, (0, 0, self.CARD_WIDTH, height), self.CARD_RADIUS, self.BG_COLOR)

            y = self.CARD_PADDING
            # Category badge
            cat_color = self.IDIOM_CATEGORY_COLORS.get(category, self.IDIOM_CATEGORY_COLORS["idiom"])
            cat_label = self.IDIOM_CATEGORY_LABELS.get(category, category).upper()
            badge_bbox = self.font_small.getbbox(cat_label)
            badge_w = badge_bbox[2] - badge_bbox[0] + 16
            self._draw_rounded_rect(draw, (self.CARD_PADDING, y, self.CARD_PADDING + badge_w, y + 22), 6, cat_color)
            draw.text((self.CARD_PADDING + 8, y + 3), cat_label, font=self.font_small, fill=self.TEXT_WHITE)
            y += 32

            # Idiom text
            draw.text((self.CARD_PADDING, y), text, font=self.font_title, fill=self.TEXT_AMBER)
            y += 36
            y += 8

            # Meaning
            if meaning:
                lines = self._wrap_text(meaning, self.font_body, content_width)
                for line in lines[:3]:
                    draw.text((self.CARD_PADDING, y), line, font=self.font_body, fill=self.TEXT_MUTED)
                    y += 22
                y += 4
            if meaning_zh:
                lines = self._wrap_text(meaning_zh, self.font_zh_body, content_width)
                for line in lines[:2]:
                    draw.text((self.CARD_PADDING, y), line, font=self.font_zh_body, fill=self.TEXT_YELLOW)
                    y += 24

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            logger.debug(f"Saved idiom card: {output_path}")
        elif card_type == "insight":
            # Render insight as a compact card
            title = card_data.get("title", "")
            content = card_data.get("content", "")
            category = card_data.get("category", "general")

            content_width = self.CARD_WIDTH - 2 * self.CARD_PADDING
            height = self.CARD_PADDING + 32 + 36 + 12
            if content:
                lines = self._wrap_text(content, self.font_body, content_width)
                height += min(len(lines), 4) * 22
            height += self.CARD_PADDING
            height = max(height, 180)

            img = Image.new("RGBA", (self.CARD_WIDTH, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            self._draw_rounded_rect(draw, (0, 0, self.CARD_WIDTH, height), self.CARD_RADIUS, self.BG_COLOR)

            y = self.CARD_PADDING
            # Category badge
            badge_bbox = self.font_small.getbbox(category.upper())
            badge_w = badge_bbox[2] - badge_bbox[0] + 16
            self._draw_rounded_rect(
                draw, (self.CARD_PADDING, y, self.CARD_PADDING + badge_w, y + 22),
                6, (168, 85, 247, 128),
            )
            draw.text((self.CARD_PADDING + 8, y + 3), category.upper(), font=self.font_small, fill=self.TEXT_WHITE)
            y += 32

            # Title
            draw.text((self.CARD_PADDING, y), title, font=self.font_title, fill=self.TEXT_WHITE)
            y += 36
            y += 8

            # Content
            if content:
                lines = self._wrap_text(content, self.font_body, content_width)
                for line in lines[:4]:
                    draw.text((self.CARD_PADDING, y), line, font=self.font_body, fill=self.TEXT_MUTED)
                    y += 22

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            logger.debug(f"Saved insight card: {output_path}")
        else:
            logger.warning(f"Unknown card type: {card_type}, falling back to entity renderer")
            localizations = card_data.get("localizations", {})
            zh_loc = localizations.get("zh", {})
            self.render_entity_card(
                name=card_data.get("name", card_data.get("text", "")),
                entity_type=card_data.get("entity_type", "other"),
                description=card_data.get("description", card_data.get("content", "")),
                name_zh=zh_loc.get("name"),
                description_zh=zh_loc.get("description"),
                output_path=output_path,
            )

        return output_path

    def render_full_panel_card(
        self,
        card_data: dict,
        card_type: str,
        panel_width: int,
        panel_height: int,
        output_path: Path,
    ) -> Path:
        """Render a full-detail panel card for WYSIWYG export.

        Args:
            card_data: Card data dictionary
            card_type: "word", "entity", "idiom", or "insight"
            panel_width: Width of the panel area
            panel_height: Height of the panel area
            output_path: Path to save the image

        Returns:
            Path to the saved image
        """
        if card_type == "word":
            self.render_full_word_card(card_data, panel_width, panel_height, output_path)
        elif card_type == "entity":
            self.render_full_entity_card(card_data, panel_width, panel_height, output_path)
        elif card_type == "idiom":
            self.render_full_idiom_card(card_data, panel_width, panel_height, output_path)
        elif card_type == "insight":
            self.render_full_insight_card(card_data, panel_width, panel_height, output_path)
        else:
            logger.warning(f"Unknown card type for full panel: {card_type}, falling back to entity")
            self.render_full_entity_card(card_data, panel_width, panel_height, output_path)

        return output_path
