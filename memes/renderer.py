"""Core meme rendering - draws text onto meme templates."""

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MEMES_DIR = Path(__file__).parent
TEMPLATES_DIR = MEMES_DIR / "templates"
FONT_PATH = MEMES_DIR / "fonts" / "Anton-Regular.ttf"


@dataclass
class TextBox:
    label: str
    x: int
    y: int
    width: int
    height: int
    rotation: int = 0


@dataclass
class Template:
    image: str
    text_boxes: list[TextBox]


def _wrap_text_by_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Word-wrap text based on actual measured pixel width, not character count."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current_line = words[0]
        for word in words[1:]:
            candidate = current_line + " " + word
            if draw.textlength(candidate, font=font) <= max_width:
                current_line = candidate
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
    return lines


def _get_line_height(font: ImageFont.FreeTypeFont) -> float:
    """Get line height from actual font metrics."""
    ascent, descent = font.getmetrics()
    return (ascent + descent) * 1.15


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: Path,
    box_width: int,
    box_height: int,
    max_font_size: int = 80,
    min_font_size: int = 16,
    max_lines: int = 4,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Find the largest font size that fits the text in the box, with word wrapping."""
    for size in range(max_font_size, min_font_size - 1, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap_text_by_width(draw, text, font, box_width)

        if len(lines) > max_lines:
            continue

        line_height = _get_line_height(font)
        total_height = line_height * len(lines)
        if total_height > box_height:
            continue

        if all(draw.textlength(line, font=font) <= box_width for line in lines):
            return font, lines

    # Fall back to minimum size
    font = ImageFont.truetype(str(font_path), min_font_size)
    lines = _wrap_text_by_width(draw, text, font, box_width)
    return font, lines


def _draw_outlined_text(
    draw: ImageDraw.ImageDraw,
    x: float,
    y: float,
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: str = "white",
    outline: str = "black",
    outline_width: int | None = None,
):
    """Draw text with an outline (the classic meme look)."""
    if outline_width is None:
        outline_width = max(1, font.size // 20)
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


def render_meme(template: Template, texts: dict[str, str]) -> bytes:
    """Render a meme from a template and a dict of label->text.

    Returns:
        PNG image bytes
    """
    img_path = TEMPLATES_DIR / template.image
    img = Image.open(img_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    for box in template.text_boxes:
        if box.label not in texts:
            continue
        text = texts[box.label]
        padding = 8

        if box.rotation:
            # Render text onto a temporary image, rotate, then paste
            text_img = Image.new("RGBA", (box.width, box.height), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_img)
            font, lines = _fit_text(
                text_draw, text.upper(), FONT_PATH,
                box.width - padding * 2, box.height - padding * 2,
            )

            line_height = _get_line_height(font)
            total_text_height = line_height * len(lines)
            y_off = (box.height - total_text_height) / 2

            for line in lines:
                line_width = text_draw.textlength(line, font=font)
                x_off = (box.width - line_width) / 2
                _draw_outlined_text(text_draw, x_off, y_off, line, font)
                y_off += line_height

            rotated = text_img.rotate(-box.rotation, expand=True, resample=Image.BICUBIC)
            cx = box.x + box.width // 2
            cy = box.y + box.height // 2
            paste_x = cx - rotated.width // 2
            paste_y = cy - rotated.height // 2
            img.paste(rotated, (paste_x, paste_y), rotated)
        else:
            font, lines = _fit_text(
                draw, text.upper(), FONT_PATH,
                box.width - padding * 2, box.height - padding * 2,
            )

            line_height = _get_line_height(font)
            total_text_height = line_height * len(lines)
            y_offset = box.y + (box.height - total_text_height) / 2

            for line in lines:
                line_width = draw.textlength(line, font=font)
                x_offset = box.x + (box.width - line_width) / 2
                _draw_outlined_text(draw, x_offset, y_offset, line, font)
                y_offset += line_height

    # Convert to RGB for PNG output
    output = Image.new("RGB", img.size, (0, 0, 0))
    output.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)

    buf = io.BytesIO()
    output.save(buf, format="PNG")
    return buf.getvalue()
