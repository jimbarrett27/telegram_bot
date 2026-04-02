"""Core meme rendering - draws text onto meme templates."""

import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MEMES_DIR = Path(__file__).parent
TEMPLATES_DIR = MEMES_DIR / "templates"
METADATA_PATH = TEMPLATES_DIR / "metadata.json"
FONT_PATH = MEMES_DIR / "fonts" / "Anton-Regular.ttf"


def load_metadata() -> dict:
    with open(METADATA_PATH) as f:
        return json.load(f)


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    box_width: int,
    box_height: int,
    max_font_size: int = 80,
    min_font_size: int = 16,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Find the largest font size that fits the text in the box, with word wrapping."""
    for size in range(max_font_size, min_font_size - 1, -2):
        font = ImageFont.truetype(str(font_path), size)
        # Estimate characters per line from average char width
        avg_char_width = font.getlength("A")
        chars_per_line = max(1, int(box_width / avg_char_width))
        lines = []
        for paragraph in text.split("\n"):
            lines.extend(textwrap.wrap(paragraph, width=chars_per_line) or [""])

        # Check if all lines fit vertically
        line_height = size * 1.2
        total_height = line_height * len(lines)
        if total_height > box_height:
            continue

        # Check if all lines fit horizontally
        fits = all(draw.textlength(line, font=font) <= box_width for line in lines)
        if fits:
            return font, lines

    # Fall back to minimum size
    font = ImageFont.truetype(str(font_path), min_font_size)
    avg_char_width = font.getlength("A")
    chars_per_line = max(1, int(box_width / avg_char_width))
    lines = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, width=chars_per_line) or [""])
    return font, lines


def _draw_outlined_text(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str = "white",
    outline: str = "black",
    outline_width: int = 3,
):
    """Draw text with an outline (the classic meme look)."""
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


def render_meme(template_name: str, texts: list[str]) -> bytes:
    """Render a meme from a template name and list of text strings.

    Args:
        template_name: Key in metadata.json (e.g. "drake")
        texts: List of text strings, one per text_box defined in metadata

    Returns:
        PNG image bytes
    """
    metadata = load_metadata()
    if template_name not in metadata:
        available = ", ".join(metadata.keys()) or "(none)"
        raise ValueError(f"Unknown template '{template_name}'. Available: {available}")

    template = metadata[template_name]
    text_boxes = template["text_boxes"]

    if len(texts) > len(text_boxes):
        raise ValueError(
            f"Template '{template_name}' has {len(text_boxes)} text boxes "
            f"but got {len(texts)} texts"
        )

    img_path = TEMPLATES_DIR / template["image"]
    img = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    for text, box in zip(texts, text_boxes):
        bx, by, bw, bh = box["x"], box["y"], box["width"], box["height"]
        padding = 8
        font, lines = _fit_text(
            draw, text.upper(), FONT_PATH, bw - padding * 2, bh - padding * 2
        )

        line_height = font.size * 1.2
        total_text_height = line_height * len(lines)
        # Center text vertically in the box
        y_offset = by + (bh - total_text_height) / 2

        for line in lines:
            line_width = draw.textlength(line, font=font)
            # Center text horizontally in the box
            x_offset = bx + (bw - line_width) / 2
            _draw_outlined_text(draw, x_offset, y_offset, line, font)
            y_offset += line_height

    # Convert to RGB for PNG output
    output = Image.new("RGB", img.size, (0, 0, 0))
    output.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)

    import io
    buf = io.BytesIO()
    output.save(buf, format="PNG")
    return buf.getvalue()
