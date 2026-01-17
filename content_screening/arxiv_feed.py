"""
ArXiv RSS feed fetching and processing.
"""

import time
from datetime import date
from typing import List

import feedparser  # type: ignore
from html2text import html2text

from content_screening.constants import INTERESTING_ARXIV_CATEGORIES, PV_KEYWORDS
from content_screening.models import Article, SourceType
from util.logging_util import setup_logger

logger = setup_logger(__name__)


def get_arxiv_rss_url(arxiv_category: str) -> str:
    """Get the RSS URL for an ArXiv category."""
    return f"http://rss.arxiv.org/rss/{arxiv_category}"


def make_arxiv_url(paper_id: str) -> str:
    """Create a URL to the ArXiv abstract page for a paper."""
    return f"https://arxiv.org/abs/{paper_id}"


def _extract_paper_id(entry_id: str) -> str:
    """Extract the paper ID from an RSS entry ID.

    Handles formats like:
    - oai:arXiv.org:2601.02514v1
    - http://arxiv.org/abs/2601.02514
    """
    if entry_id.startswith("oai:"):
        return entry_id.split(":")[-1]
    return entry_id.split("/")[-1]


def _extract_authors(entry: dict) -> List[str]:
    """Extract author names from an RSS entry."""
    if 'authors' in entry:
        return [author.get('name', '') for author in entry.get('authors', [])]
    elif 'author' in entry:
        return [entry['author']]
    return []


def _find_matching_keywords(text: str) -> List[str]:
    """Find PV keywords that match in the given text."""
    text_lower = text.lower()
    return [kw for kw in PV_KEYWORDS if kw in text_lower]


def _is_published_today(entry: dict) -> bool:
    """Check if an RSS entry was published today.

    Uses the published_parsed field from feedparser which provides a struct_time.
    Returns True if no date is available (to avoid filtering out entries without dates).
    """
    published_parsed = entry.get("published_parsed")
    if published_parsed is None:
        # If no date available, include the entry to be safe
        return True

    today = date.today()
    entry_date = date(published_parsed.tm_year, published_parsed.tm_mon, published_parsed.tm_mday)
    return entry_date == today


def fetch_arxiv_papers(
    categories: set = None,
    filter_by_keywords: bool = True,
    keywords: set = None
) -> List[Article]:
    """
    Fetch papers from ArXiv RSS feeds.

    Args:
        categories: ArXiv categories to fetch from. Defaults to INTERESTING_ARXIV_CATEGORIES.
        filter_by_keywords: Whether to filter by PV keywords.
        keywords: Keywords to filter by. Defaults to PV_KEYWORDS.

    Returns:
        List of Article objects matching the criteria.
    """
    if categories is None:
        categories = INTERESTING_ARXIV_CATEGORIES
    if keywords is None:
        keywords = PV_KEYWORDS

    seen_ids = set()
    articles = []
    discovered_at = int(time.time())

    for category in categories:
        url = get_arxiv_rss_url(category)
        try:
            rss_content = feedparser.parse(url)
        except Exception as e:
            logger.error(f"Error fetching RSS for {category}: {e}")
            continue

        for entry in rss_content.get("entries", []):
            paper_id = _extract_paper_id(entry.get("id", ""))

            if not paper_id or paper_id in seen_ids:
                continue
            seen_ids.add(paper_id)

            # Only consider papers published today
            if not _is_published_today(entry):
                continue

            title = entry.get("title", "").strip()
            abstract = html2text(entry.get("summary", "")).strip()

            if filter_by_keywords:
                search_text = f"{title} {abstract}"
                matching_keywords = _find_matching_keywords(search_text)
                if not matching_keywords:
                    continue
            else:
                matching_keywords = []

            article = Article(
                external_id=paper_id,
                source_type=SourceType.ARXIV,
                title=title,
                abstract=abstract,
                url=make_arxiv_url(paper_id),
                authors=_extract_authors(entry),
                categories=[category],
                keywords_matched=matching_keywords,
                discovered_at=discovered_at,
            )
            articles.append(article)

    logger.info(f"Fetched {len(articles)} papers matching criteria from {len(categories)} categories")
    return articles
