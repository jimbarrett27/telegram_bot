"""Fetch top news stories to feed into the tapestry generator."""

import logging

import feedparser  # type: ignore
from html2text import html2text

logger = logging.getLogger(__name__)

BBC_TOP_STORIES_RSS = "https://feeds.bbci.co.uk/news/rss.xml"


def fetch_bbc_stories(n: int = None, feed_url: str = BBC_TOP_STORIES_RSS) -> list[dict]:
    """Return top BBC stories as ``{'title', 'summary', 'link'}`` dicts.

    ``n`` caps the number of stories returned (defaults to the whole feed).
    """
    feed = feedparser.parse(feed_url)
    stories = []
    for entry in feed.entries:
        title = entry.get("title")
        link = entry.get("link")
        if not title or not link:
            continue
        stories.append({
            "title": title.strip(),
            "summary": html2text(entry.get("summary", "")).strip(),
            "link": link,
        })
        if n is not None and len(stories) >= n:
            break

    logger.info("Fetched %d BBC stories from %s", len(stories), feed_url)
    return stories
