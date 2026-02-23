"""Deterministic markdown campaign loader.

Reads pre-built .md files from dnd/campaigns/ and parses them into
structured sections for storage in the database. No LLM or PDF
library needed at runtime.
"""

from pathlib import Path

from dnd.database import store_campaign_sections
from util.constants import REPO_ROOT
from util.logging_util import setup_logger

logger = setup_logger(__name__)

CAMPAIGNS_DIR = REPO_ROOT / "dnd" / "campaigns"


def list_available_campaigns() -> list[str]:
    """List *.md files in CAMPAIGNS_DIR (stems, sorted)."""
    if not CAMPAIGNS_DIR.exists():
        return []
    return sorted(p.stem for p in CAMPAIGNS_DIR.glob("*.md"))


def get_campaign_path(campaign_name: str) -> Path | None:
    """Find a campaign .md by exact or case-insensitive partial match."""
    exact = CAMPAIGNS_DIR / f"{campaign_name}.md"
    if exact.exists():
        return exact

    name_lower = campaign_name.lower()
    for md in CAMPAIGNS_DIR.glob("*.md"):
        if name_lower in md.stem.lower():
            return md

    return None


def parse_campaign_markdown(md_path: Path) -> list[dict]:
    """Parse .md into [{"title": str, "content": str}, ...].

    Split on lines starting with '## '. Text before first ## becomes
    an 'Introduction' section. The level-1 heading (# Title) is included
    in the introduction content.
    """
    text = md_path.read_text()
    lines = text.split("\n")

    sections: list[dict] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            # Save previous section
            content = "\n".join(current_lines).strip()
            if content:
                sections.append({
                    "title": current_title or "Introduction",
                    "content": content,
                })
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save final section
    content = "\n".join(current_lines).strip()
    if content:
        sections.append({
            "title": current_title or "Introduction",
            "content": content,
        })

    return sections


def load_campaign(game_id: int, campaign_name: str) -> str:
    """Find campaign, parse, store sections, return summary from first 4 sections.

    Raises:
        FileNotFoundError: If no matching campaign is found (message lists available).
    """
    md_path = get_campaign_path(campaign_name)
    if md_path is None:
        available = list_available_campaigns()
        raise FileNotFoundError(
            f"Campaign '{campaign_name}' not found. "
            f"Available: {', '.join(available) or 'none'}"
        )

    sections = parse_campaign_markdown(md_path)
    store_campaign_sections(game_id, sections)

    summary_parts = []
    for section in sections[:4]:
        summary_parts.append(f"## {section['title']}\n{section['content']}")

    summary = (
        f"Adventure: {md_path.stem}\n\n"
        + "\n\n".join(summary_parts)
        + "\n\n(Use the lookup_campaign tool to access more adventure details.)"
    )

    logger.info(f"Loaded campaign {md_path.name}: {len(sections)} sections")
    return summary
