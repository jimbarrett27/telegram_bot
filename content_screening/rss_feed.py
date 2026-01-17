"""
Generic RSS feed fetching and processing.
"""

import hashlib
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

import feedparser  # type: ignore
import yaml
from html2text import html2text

from content_screening.constants import MODULE_ROOT, PV_KEYWORDS
from content_screening.models import Article, SourceType
from util.logging_util import setup_logger

logger = setup_logger(__name__)

FEEDS_CONFIG_PATH = MODULE_ROOT / "data" / "feeds.yaml"


@dataclass
class FeedConfig:
    """Configuration for a single RSS feed."""
    name: str
    url: str
    category: Optional[str] = None


def load_feed_configs(config_path: Path = FEEDS_CONFIG_PATH) -> List[FeedConfig]:
    """Load feed configurations from YAML file."""
    if not config_path.exists():
        logger.warning(f"Feed config not found at {config_path}")
        return []

    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    feeds = []
    for feed_data in data.get("feeds", []):
        feeds.append(FeedConfig(
            name=feed_data["name"],
            url=feed_data["url"],
            category=feed_data.get("category"),
        ))
    return feeds


def _generate_external_id(entry: dict, feed_url: str) -> str:
    """Generate a unique external ID for an RSS entry.

    Uses the entry's id/guid if available, otherwise creates a hash
    from the URL and title.
    """
    entry_id = entry.get("id") or entry.get("link")
    if entry_id:
        return entry_id

    # Fallback: hash of feed URL + title
    title = entry.get("title", "")
    hash_input = f"{feed_url}:{title}"
    return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


def _extract_authors(entry: dict) -> List[str]:
    """Extract author names from an RSS entry.

    Handles various formats:
    - String with semicolon/comma separated names (IEEE)
    - List of dicts with 'name' key (Lancet, Wiley)
    - Single 'author' string
    """
    if "authors" in entry:
        authors = entry["authors"]
        if isinstance(authors, str):
            # IEEE format: "Name1;Name2;" or "Name1, Name2"
            authors = authors.replace(";", ",")
            return [a.strip() for a in authors.split(",") if a.strip()]
        elif isinstance(authors, list):
            # List of dicts with 'name' key
            result = []
            for author in authors:
                if isinstance(author, dict):
                    name = author.get("name", "")
                    # Wiley format may have newlines
                    name = name.replace("\n", ", ")
                    result.append(name.strip())
                elif isinstance(author, str):
                    result.append(author.strip())
            return [a for a in result if a]
    elif "author" in entry:
        author = entry["author"]
        if isinstance(author, str):
            return [author.strip()] if author.strip() else []
    return []


def _extract_summary(entry: dict) -> str:
    """Extract and clean summary/description from an RSS entry."""
    summary = entry.get("summary", "") or entry.get("description", "")
    if not summary:
        return ""
    # Convert HTML to plain text
    return html2text(summary).strip()


def _find_matching_keywords(text: str) -> List[str]:
    """Find PV keywords that match in the given text."""
    text_lower = text.lower()
    return [kw for kw in PV_KEYWORDS if kw in text_lower]


def _is_published_today(entry: dict) -> bool:
    """Check if an RSS entry was published exactly today.

    Uses the published_parsed field from feedparser which provides a struct_time.
    Returns False if no date is available or if the date is not exactly today.
    """
    published_parsed = entry.get("published_parsed")
    if published_parsed is None:
        # No date available, exclude the entry
        return False

    today = date.today()
    entry_date = date(published_parsed.tm_year, published_parsed.tm_mon, published_parsed.tm_mday)
    return entry_date == today


def fetch_rss_articles(
    feed_configs: List[FeedConfig] = None,
    filter_by_keywords: bool = True,
    keywords: set = None
) -> List[Article]:
    """
    Fetch articles from RSS feeds.

    Args:
        feed_configs: Feed configurations to fetch from. Defaults to loading from YAML.
        filter_by_keywords: Whether to filter by PV keywords.
        keywords: Keywords to filter by. Defaults to PV_KEYWORDS.

    Returns:
        List of Article objects matching the criteria.
    """
    if feed_configs is None:
        feed_configs = load_feed_configs()
    if keywords is None:
        keywords = PV_KEYWORDS

    if not feed_configs:
        logger.warning("No RSS feeds configured")
        return []

    seen_ids = set()
    articles = []
    discovered_at = int(time.time())

    for feed_config in feed_configs:
        try:
            rss_content = feedparser.parse(feed_config.url)
        except Exception as e:
            logger.error(f"Error fetching RSS for {feed_config.name}: {e}")
            continue

        status = rss_content.get("status")
        if status and status >= 400:
            logger.warning(f"HTTP {status} for feed {feed_config.name}")
            continue

        for entry in rss_content.get("entries", []):
            external_id = _generate_external_id(entry, feed_config.url)

            if external_id in seen_ids:
                continue
            seen_ids.add(external_id)

            # Only consider articles published today
            if not _is_published_today(entry):
                continue

            title = entry.get("title", "").strip()
            if not title:
                continue

            abstract = _extract_summary(entry)
            link = entry.get("link", "")
            if not link:
                continue

            if filter_by_keywords:
                search_text = f"{title} {abstract}"
                matching_keywords = _find_matching_keywords(search_text)
                if not matching_keywords:
                    continue
            else:
                matching_keywords = []

            article = Article(
                external_id=external_id,
                source_type=SourceType.RSS,
                title=title,
                abstract=abstract,
                url=link,
                authors=_extract_authors(entry),
                categories=[feed_config.name],
                keywords_matched=matching_keywords,
                discovered_at=discovered_at,
                metadata={
                    "feed_url": feed_config.url,
                    "feed_category": feed_config.category,
                    "published": entry.get("published", ""),
                },
            )
            articles.append(article)

    logger.info(f"Fetched {len(articles)} articles matching criteria from {len(feed_configs)} RSS feeds")
    return articles
