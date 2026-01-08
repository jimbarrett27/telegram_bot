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
from telegram_bot.telegram_bot import send_message_to_me
from util.logging_util import setup_logger

logger = setup_logger(__name__)


def _format_article_notification(article: Article) -> str:
    """Format an article for notification."""
    keywords_str = ", ".join(article.keywords_matched) if article.keywords_matched else "None"
    categories_str = ", ".join(article.categories) if article.categories else "Unknown"

    return f"""[Papers] New PV-related paper found!

Title: {article.title}
Categories: {categories_str}
Keywords matched: {keywords_str}

{article.url}

Reply with a rating (1-10) for how interesting you find this."""


def _notify_about_article(article: Article):
    """Send a notification about an interesting article."""
    message = _format_article_notification(article)
    send_message_to_me(message)
    create_pending_notification(article.id)
    logger.info(f"Sent notification for article: {article.external_id}")


def process_new_articles(articles: List[Article]) -> int:
    """
    Process a list of articles: insert new ones and notify.

    Returns the number of new articles processed.
    """
    new_count = 0
    for article in articles:
        if article_exists(article.source_type, article.external_id):
            logger.debug(f"Article already exists: {article.external_id}")
            continue

        article_id = insert_article(article)
        article.id = article_id
        _notify_about_article(article)
        new_count += 1

    return new_count


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
