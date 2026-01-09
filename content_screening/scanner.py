"""
Daily scan orchestration for content screening.
"""

import time
from typing import List

from content_screening.arxiv_feed import fetch_arxiv_papers
from content_screening.constants import SCAN_INTERVAL_SECONDS
from content_screening.database import (
    article_exists,
    create_pending_notification,
    get_last_scan_time,
    insert_article,
    update_scan_history,
)
from content_screening.models import Article, SourceType
from content_screening.rss_feed import fetch_rss_articles
from content_screening.screener import screen_article
from telegram_bot.telegram_bot import send_message_to_me
from util.logging_util import setup_logger

logger = setup_logger(__name__)


def _format_article_notification(article: Article) -> str:
    """Format an article for notification."""
    categories_str = ", ".join(article.categories) if article.categories else "Unknown"

    # Use appropriate label based on source type
    if article.source_type == SourceType.RSS:
        source_label = "Source"
    else:
        source_label = "Categories"

    msg = f"""[Papers] New PV-related paper found!

Title: {article.title}
{source_label}: {categories_str}"""

    if article.llm_reasoning:
        msg += f"\nWhy: {article.llm_reasoning}"

    msg += f"""

{article.url}

Reply with a rating (1-10) for how interesting you find this."""

    return msg


def _notify_about_article(article: Article):
    """Send a notification about an interesting article."""
    message = _format_article_notification(article)
    send_message_to_me(message)
    create_pending_notification(article.id)
    logger.info(f"Sent notification for article: {article.external_id}")


def process_new_articles(articles: List[Article]) -> int:
    """
    Process a list of articles: screen with LLM, insert new ones, and notify if relevant.

    Returns the number of new relevant articles notified about.
    """
    notified_count = 0
    for article in articles:
        if article_exists(article.source_type, article.external_id):
            logger.debug(f"Article already exists: {article.external_id}")
            continue

        # Screen with LLM before deciding to notify
        is_relevant, score, reasoning, tags = screen_article(article)
        article.llm_interest_score = score if is_relevant else 0.0
        article.llm_reasoning = reasoning
        article.llm_tags = tags

        # Always insert the article (for record keeping)
        article_id = insert_article(article)
        article.id = article_id

        # Only notify if LLM says it's relevant
        if is_relevant:
            _notify_about_article(article)
            notified_count += 1
        else:
            logger.info(f"Skipping notification for '{article.title[:50]}...': not PV-relevant")

    return notified_count


def run_arxiv_scan() -> tuple[int, int]:
    """
    Run a scan of ArXiv feeds.

    Returns (total_found, new_interesting) counts.
    """
    logger.info("Starting ArXiv scan")
    articles = fetch_arxiv_papers()
    total_found = len(articles)

    new_count = process_new_articles(articles)
    update_scan_history(SourceType.ARXIV, total_found, new_count)

    logger.info(f"ArXiv scan complete: {total_found} found, {new_count} new")
    return total_found, new_count


def run_rss_scan() -> tuple[int, int]:
    """
    Run a scan of RSS feeds.

    Returns (total_found, new_interesting) counts.
    """
    logger.info("Starting RSS scan")
    articles = fetch_rss_articles()
    total_found = len(articles)

    new_count = process_new_articles(articles)
    update_scan_history(SourceType.RSS, total_found, new_count)

    logger.info(f"RSS scan complete: {total_found} found, {new_count} new")
    return total_found, new_count


def is_scan_due(source_type: SourceType) -> bool:
    """Check if a scan is due for the given source type."""
    last_scan = get_last_scan_time(source_type)
    if last_scan is None:
        return True
    return (time.time() - last_scan) >= SCAN_INTERVAL_SECONDS


def run_daily_scan_if_due():
    """
    Run daily scans for all sources if they are due.

    This function is meant to be called from the main loop.
    """
    if is_scan_due(SourceType.ARXIV):
        run_arxiv_scan()
    if is_scan_due(SourceType.RSS):
        run_rss_scan()
