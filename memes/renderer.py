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


def render_meme(template_name: str, texts: dict[str, str]) -> bytes:
    """Render a meme from a template name and a dict of label->text.

    Args:
        template_name: Key in metadata.json (e.g. "drake")
        texts: Dict mapping text box labels to text strings (e.g. {"top": "Hello", "bottom": "World"})

    Returns:
        PNG image bytes
    """
    metadata = load_metadata()
    if template_name not in metadata:
        available = ", ".join(metadata.keys()) or "(none)"
        raise ValueError(f"Unknown template '{template_name}'. Available: {available}")

    template = metadata[template_name]
    text_boxes = template["text_boxes"]
    box_labels = {box["label"] for box in text_boxes}

    unknown = set(texts.keys()) - box_labels
    if unknown:
        raise ValueError(
            f"Unknown label(s) {unknown} for template '{template_name}'. "
            f"Available: {box_labels}"
        )

    img_path = TEMPLATES_DIR / template["image"]
    img = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    for box in text_boxes:
        if box["label"] not in texts:
            continue
        text = texts[box["label"]]
        bx, by, bw, bh = box["x"], box["y"], box["width"], box["height"]
        rotation = box.get("rotation", 0)
        padding = 8

        if rotation:
            # Render text onto a temporary image, rotate, then paste
            text_img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_img)
            font, lines = _fit_text(
                text_draw, text.upper(), FONT_PATH, bw - padding * 2, bh - padding * 2
            )

            line_height = font.size * 1.2
            total_text_height = line_height * len(lines)
            y_off = (bh - total_text_height) / 2

            for line in lines:
                line_width = text_draw.textlength(line, font=font)
                x_off = (bw - line_width) / 2
                _draw_outlined_text(text_draw, x_off, y_off, line, font)
                y_off += line_height

            rotated = text_img.rotate(-rotation, expand=True, resample=Image.BICUBIC)
            # Center the rotated image on the original box center
            cx = bx + bw // 2
            cy = by + bh // 2
            paste_x = cx - rotated.width // 2
            paste_y = cy - rotated.height // 2
            img.paste(rotated, (paste_x, paste_y), rotated)
        else:
            font, lines = _fit_text(
                draw, text.upper(), FONT_PATH, bw - padding * 2, bh - padding * 2
            )

            line_height = font.size * 1.2
            total_text_height = line_height * len(lines)
            y_offset = by + (bh - total_text_height) / 2

            for line in lines:
                line_width = draw.textlength(line, font=font)
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
