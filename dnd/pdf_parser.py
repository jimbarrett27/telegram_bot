"""PDF adventure parser.

Extracts text from adventure PDFs and splits into structured sections
based on heading detection (font size analysis).
"""

from pathlib import Path

import fitz

from util.constants import REPO_ROOT
from util.logging_util import setup_logger

logger = setup_logger(__name__)

ADVENTURES_DIR = REPO_ROOT / "dnd" / "adventures"

# Headings are detected by font size. Anything above this threshold
# is treated as a section heading.
HEADING_SIZE_THRESHOLD = 14.0


def list_available_adventures() -> list[str]:
    """List available adventure PDFs (without extension).

    Returns:
        List of adventure names, e.g. ["Wiebe_TheHangover"].
    """
    if not ADVENTURES_DIR.exists():
        return []
    return sorted(
        p.stem for p in ADVENTURES_DIR.glob("*.pdf")
    )


def _extract_headings_and_text(doc: fitz.Document) -> list[dict]:
    """Extract text from a PDF, identifying headings by font size.

    Returns a list of {"type": "heading"|"text", "content": str} items
    in document order.
    """
    elements = []

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                line_text_parts = []
                max_size = 0
                for span in line["spans"]:
                    text = span["text"].strip()
                    if text:
                        line_text_parts.append(text)
                        max_size = max(max_size, span["size"])

                line_text = " ".join(line_text_parts)
                if not line_text:
                    continue

                if max_size > HEADING_SIZE_THRESHOLD:
                    elements.append({"type": "heading", "content": line_text})
                else:
                    elements.append({"type": "text", "content": line_text})

    return elements


def _merge_split_headings(elements: list[dict]) -> list[dict]:
    """Merge consecutive heading elements (handles headings split across lines)."""
    merged = []
    for elem in elements:
        if (elem["type"] == "heading"
                and merged
                and merged[-1]["type"] == "heading"):
            merged[-1]["content"] += " " + elem["content"]
        else:
            merged.append(dict(elem))
    return merged


def _elements_to_sections(elements: list[dict]) -> list[dict]:
    """Convert a list of heading/text elements into sections.

    Returns list of {"title": str, "content": str} dicts.
    """
    sections = []
    current_title = None
    current_content = []

    for elem in elements:
        if elem["type"] == "heading":
            # Save previous section
            if current_title is not None or current_content:
                sections.append({
                    "title": current_title or "Introduction",
                    "content": "\n".join(current_content).strip(),
                })
            current_title = elem["content"]
            current_content = []
        else:
            current_content.append(elem["content"])

    # Save final section
    if current_title is not None or current_content:
        sections.append({
            "title": current_title or "Introduction",
            "content": "\n".join(current_content).strip(),
        })

    # Filter out empty sections
    sections = [s for s in sections if s["content"]]

    return sections


def parse_adventure_pdf(pdf_path: Path) -> list[dict]:
    """Parse a PDF adventure into structured sections.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of {"title": str, "content": str} dicts, ordered as they
        appear in the document. The first section typically serves as
        the adventure overview/summary.
    """
    doc = fitz.open(str(pdf_path))
    elements = _extract_headings_and_text(doc)
    elements = _merge_split_headings(elements)
    sections = _elements_to_sections(elements)
    doc.close()

    logger.info(f"Parsed {pdf_path.name}: {len(sections)} sections")
    return sections


def get_adventure_path(adventure_name: str) -> Path | None:
    """Get the path to an adventure PDF by name.

    Tries exact match first, then case-insensitive partial match.

    Returns:
        Path to the PDF, or None if not found.
    """
    # Exact match
    exact = ADVENTURES_DIR / f"{adventure_name}.pdf"
    if exact.exists():
        return exact

    # Case-insensitive partial match
    name_lower = adventure_name.lower()
    for pdf in ADVENTURES_DIR.glob("*.pdf"):
        if name_lower in pdf.stem.lower():
            return pdf

    return None
