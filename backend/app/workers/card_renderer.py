"""Card renderer for video export - generates PNG images of word/entity cards."""

import io
from pathlib import Path
from typing import Optional, Tuple, List
from loguru import logger

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("Pillow not installed. Card rendering will not be available.")


class CardRenderer:
    """Renderer for generating card images for video overlay."""

    # Card dimensions
    CARD_WIDTH = 400
    CARD_PADDING = 24
    CARD_RADIUS = 16

    # Colors (RGBA)
    BG_COLOR = (26, 39, 68, 230)  # #1a2744 with 90% opacity
    TEXT_WHITE = (255, 255, 255, 255)
    TEXT_MUTED = (255, 255, 255, 153)  # 60% opacity
    TEXT_YELLOW = (250, 204, 21, 255)  # #facc15
    TEXT_BLUE = (147, 197, 253, 255)  # blue-300
    TEXT_PURPLE = (196, 181, 253, 255)  # purple-300
    TEXT_GREEN = (134, 239, 172, 255)  # green-300
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

    def _load_fonts(self) -> None:
        """Load fonts with fallbacks."""
        # Try to load custom fonts, fallback to system fonts
        try:
            # Primary fonts
            self.font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
            self.font_body = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
            self.font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
            self.font_ipa = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)

            # Chinese fonts
            self.font_zh_title = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 24)
            self.font_zh_body = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 18)
            self.font_zh_small = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 14)
        except OSError:
            # Fallback to default font
            logger.warning("Custom fonts not found, using default font")
            self.font_title = ImageFont.load_default()
            self.font_body = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
            self.font_ipa = ImageFont.load_default()
            self.font_zh_title = ImageFont.load_default()
            self.font_zh_body = ImageFont.load_default()
            self.font_zh_small = ImageFont.load_default()

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

    def render_word_card(
        self,
        word: str,
        ipa: Optional[str] = None,
        cefr_level: Optional[str] = None,
        senses: Optional[List[dict]] = None,
        output_path: Optional[Path] = None,
    ) -> Image.Image:
        """Render a word card as PNG.

        Args:
            word: The word
            ipa: IPA pronunciation
            cefr_level: CEFR level (A1-C2)
            senses: List of word senses with definition_zh, definition, examples
            output_path: Optional path to save the image

        Returns:
            PIL Image object
        """
        # Calculate card height based on content
        content_width = self.CARD_WIDTH - 2 * self.CARD_PADDING
        y = self.CARD_PADDING

        # Estimate height
        height = self.CARD_PADDING  # Top padding
        height += 36  # Word title
        if ipa:
            height += 24  # IPA
        if cefr_level:
            height += 28  # CEFR badge
        height += 16  # Divider spacing

        # Senses
        if senses:
            for sense in senses[:2]:  # Max 2 senses
                height += 28  # POS header
                if sense.get("definition_zh"):
                    lines = self._wrap_text(sense["definition_zh"], self.font_zh_body, content_width - 20)
                    height += len(lines) * 24
                if sense.get("definition"):
                    lines = self._wrap_text(sense["definition"], self.font_body, content_width - 20)
                    height += len(lines) * 22
                # Example
                if sense.get("examples") and sense["examples"]:
                    height += 40  # One example
                height += 16  # Spacing

        height += self.CARD_PADDING  # Bottom padding
        height = max(height, 200)  # Minimum height

        # Create image with transparency
        img = Image.new("RGBA", (self.CARD_WIDTH, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw background
        self._draw_rounded_rect(
            draw,
            (0, 0, self.CARD_WIDTH, height),
            self.CARD_RADIUS,
            self.BG_COLOR,
        )

        # Draw word title
        draw.text((self.CARD_PADDING, y), word, font=self.font_title, fill=self.TEXT_WHITE)
        y += 36

        # Draw IPA
        if ipa:
            draw.text((self.CARD_PADDING, y), ipa, font=self.font_ipa, fill=self.TEXT_BLUE)
            y += 24

        # Draw CEFR level badge
        if cefr_level:
            badge_text = cefr_level.upper()
            badge_bbox = self.font_small.getbbox(badge_text)
            badge_width = badge_bbox[2] - badge_bbox[0] + 16
            badge_height = 22
            self._draw_rounded_rect(
                draw,
                (self.CARD_PADDING, y, self.CARD_PADDING + badge_width, y + badge_height),
                6,
                (168, 85, 247, 77),  # purple with 30% opacity
            )
            draw.text(
                (self.CARD_PADDING + 8, y + 3),
                badge_text,
                font=self.font_small,
                fill=self.TEXT_PURPLE,
            )
            y += 28

        y += 8  # Spacing before senses

        # Draw senses
        if senses:
            for i, sense in enumerate(senses[:2]):
                # Part of speech
                pos = sense.get("part_of_speech", "")
                if pos:
                    draw.text(
                        (self.CARD_PADDING, y),
                        pos.upper(),
                        font=self.font_small,
                        fill=self.TEXT_MUTED,
                    )
                    # Draw divider line
                    pos_bbox = self.font_small.getbbox(pos.upper())
                    line_x = self.CARD_PADDING + pos_bbox[2] - pos_bbox[0] + 12
                    draw.line(
                        [(line_x, y + 8), (self.CARD_WIDTH - self.CARD_PADDING, y + 8)],
                        fill=self.DIVIDER_COLOR,
                        width=1,
                    )
                    y += 24

                # Chinese definition (primary)
                if sense.get("definition_zh"):
                    def_text = f"{i + 1}. {sense['definition_zh']}"
                    lines = self._wrap_text(def_text, self.font_zh_body, content_width - 20)
                    for line in lines:
                        draw.text(
                            (self.CARD_PADDING + 8, y),
                            line,
                            font=self.font_zh_body,
                            fill=self.TEXT_WHITE,
                        )
                        y += 24

                # English definition (secondary)
                if sense.get("definition") and sense["definition"] != sense.get("definition_zh"):
                    lines = self._wrap_text(sense["definition"], self.font_body, content_width - 30)
                    for line in lines[:2]:  # Max 2 lines
                        draw.text(
                            (self.CARD_PADDING + 16, y),
                            line,
                            font=self.font_body,
                            fill=self.TEXT_MUTED,
                        )
                        y += 22

                # Example sentence
                examples = sense.get("examples", [])
                examples_zh = sense.get("examples_zh", [])
                if examples:
                    example = examples[0]
                    # Draw quote bar
                    draw.rectangle(
                        (self.CARD_PADDING + 12, y + 2, self.CARD_PADDING + 14, y + 36),
                        fill=self.DIVIDER_COLOR,
                    )
                    # English example
                    ex_lines = self._wrap_text(f'"{example}"', self.font_small, content_width - 40)
                    draw.text(
                        (self.CARD_PADDING + 20, y),
                        ex_lines[0] if ex_lines else "",
                        font=self.font_small,
                        fill=self.TEXT_MUTED,
                    )
                    y += 18
                    # Chinese translation of example
                    if examples_zh and examples_zh[0]:
                        draw.text(
                            (self.CARD_PADDING + 20, y),
                            examples_zh[0][:40] + ("..." if len(examples_zh[0]) > 40 else ""),
                            font=self.font_zh_small,
                            fill=self.TEXT_YELLOW,
                        )
                        y += 18

                y += 12  # Spacing between senses

        # Save if output path provided
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
        """Render an entity card as PNG.

        Args:
            name: Entity name
            entity_type: Entity type (person, place, etc.)
            description: English description
            name_zh: Chinese name
            description_zh: Chinese description
            image_url: Optional image URL (not fetched, placeholder shown)
            output_path: Optional path to save the image

        Returns:
            PIL Image object
        """
        content_width = self.CARD_WIDTH - 2 * self.CARD_PADDING

        # Calculate height
        height = self.CARD_PADDING
        height += 32  # Type badge area
        height += 36  # Name
        if name_zh and name_zh != name:
            height += 24  # Chinese name
        height += 12  # Spacing

        if description:
            lines = self._wrap_text(description, self.font_body, content_width)
            height += min(len(lines), 3) * 22  # Max 3 lines
            height += 8

        if description_zh:
            lines = self._wrap_text(description_zh, self.font_zh_body, content_width)
            height += min(len(lines), 2) * 24  # Max 2 lines

        height += self.CARD_PADDING
        height = max(height, 180)

        # Create image
        img = Image.new("RGBA", (self.CARD_WIDTH, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw background
        self._draw_rounded_rect(
            draw,
            (0, 0, self.CARD_WIDTH, height),
            self.CARD_RADIUS,
            self.BG_COLOR,
        )

        y = self.CARD_PADDING

        # Draw entity type badge
        type_color = self.ENTITY_TYPE_COLORS.get(entity_type.lower(), self.ENTITY_TYPE_COLORS["other"])
        badge_text = entity_type.upper()
        badge_bbox = self.font_small.getbbox(badge_text)
        badge_width = badge_bbox[2] - badge_bbox[0] + 16
        badge_height = 22
        self._draw_rounded_rect(
            draw,
            (self.CARD_PADDING, y, self.CARD_PADDING + badge_width, y + badge_height),
            6,
            type_color,
        )
        draw.text(
            (self.CARD_PADDING + 8, y + 3),
            badge_text,
            font=self.font_small,
            fill=self.TEXT_WHITE,
        )
        y += 32

        # Draw name
        draw.text((self.CARD_PADDING, y), name, font=self.font_title, fill=self.TEXT_WHITE)
        y += 36

        # Draw Chinese name
        if name_zh and name_zh != name:
            draw.text((self.CARD_PADDING, y), name_zh, font=self.font_zh_body, fill=self.TEXT_YELLOW)
            y += 24

        y += 8

        # Draw English description
        if description:
            lines = self._wrap_text(description, self.font_body, content_width)
            for line in lines[:3]:
                draw.text((self.CARD_PADDING, y), line, font=self.font_body, fill=self.TEXT_MUTED)
                y += 22
            y += 4

        # Draw Chinese description
        if description_zh:
            lines = self._wrap_text(description_zh, self.font_zh_body, content_width)
            for line in lines[:2]:
                draw.text((self.CARD_PADDING, y), line, font=self.font_zh_body, fill=self.TEXT_MUTED)
                y += 24

        # Save if output path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG")
            logger.debug(f"Saved entity card: {output_path}")

        return img

    def render_pinned_card(
        self,
        card_data: dict,
        card_type: str,
        output_path: Path,
    ) -> Path:
        """Render a pinned card based on its type and data.

        Args:
            card_data: Card data dictionary (WordCard or EntityCard)
            card_type: "word" or "entity"
            output_path: Path to save the image

        Returns:
            Path to the saved image
        """
        if card_type == "word":
            # Extract word card data
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
        else:
            # Entity card
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

        return output_path
