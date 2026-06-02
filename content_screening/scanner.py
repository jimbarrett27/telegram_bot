"""
Daily scan orchestration for content screening.
"""

import time
from typing import List

from sqlalchemy import func, select

from content_screening.arxiv_feed import fetch_arxiv_papers
from content_screening.constants import SCAN_INTERVAL_SECONDS
from content_screening.database import (
    article_exists,
    get_last_scan_time,
    insert_article,
    update_scan_history,
)
from content_screening.db_engine import get_session
from content_screening.models import Article, SourceType
from content_screening.orm_models import ArticleORM
from content_screening.rss_feed import fetch_rss_articles
from content_screening.screener import screen_article
from util.logging_util import setup_logger

logger = setup_logger(__name__)


def process_new_articles(articles: List[Article]) -> tuple[int, int]:
    """Screen new (unseen) articles with the LLM and insert them.

    Triage replaces the old per-article Telegram notifications, so nothing is
    sent here — papers simply land in the DB for the triage queue. Returns
    ``(new_inserted, new_relevant)``.
    """
    new_inserted = 0
    new_relevant = 0
    for article in articles:
        if article_exists(article.source_type, article.external_id):
            logger.debug(f"Article already exists: {article.external_id}")
            continue

        is_relevant, score, reasoning, tags, suggested_depth = screen_article(article)
        article.llm_interest_score = score if is_relevant else 0.0
        article.llm_reasoning = reasoning
        article.llm_tags = tags
        article.suggested_depth = suggested_depth

        # Always insert (relevant ones enter the triage queue; the rest are kept
        # for record-keeping with score 0).
        article.id = insert_article(article)
        new_inserted += 1
        if is_relevant:
            new_relevant += 1

    return new_inserted, new_relevant


def run_arxiv_scan() -> tuple[int, int, int]:
    """Scan ArXiv feeds. Returns (total_found, new_inserted, new_relevant)."""
    logger.info("Starting ArXiv scan")
    articles = fetch_arxiv_papers()
    total_found = len(articles)
    new_inserted, new_relevant = process_new_articles(articles)
    update_scan_history(SourceType.ARXIV, total_found, new_relevant)
    logger.info(f"ArXiv scan complete: {total_found} found, {new_inserted} new, {new_relevant} relevant")
    return total_found, new_inserted, new_relevant


def run_rss_scan() -> tuple[int, int, int]:
    """Scan RSS feeds. Returns (total_found, new_inserted, new_relevant)."""
    logger.info("Starting RSS scan")
    articles = fetch_rss_articles()
    total_found = len(articles)
    new_inserted, new_relevant = process_new_articles(articles)
    update_scan_history(SourceType.RSS, total_found, new_relevant)
    logger.info(f"RSS scan complete: {total_found} found, {new_inserted} new, {new_relevant} relevant")
    return total_found, new_inserted, new_relevant


def count_pending_triage() -> int:
    """How many screened-relevant papers are awaiting a triage decision."""
    with get_session() as session:
        return session.scalar(
            select(func.count())
            .select_from(ArticleORM)
            .where(ArticleORM.status == "pending", ArticleORM.llm_interest_score > 0)
        ) or 0


def run_full_scan() -> dict:
    """Run all source scans (silently) and return summary counts."""
    _, a_new, a_rel = run_arxiv_scan()
    _, r_new, r_rel = run_rss_scan()
    return {
        "new": a_new + r_new,
        "relevant": a_rel + r_rel,
        "pending": count_pending_triage(),
    }


def format_scan_summary(counts: dict) -> str:
    """The single daily message: new papers found + total awaiting triage."""
    return (
        "📚 Daily paper scan\n"
        f"New papers: {counts['new']} ({counts['relevant']} relevant for triage)\n"
        f"Awaiting triage: {counts['pending']}"
    )


def is_scan_due(source_type: SourceType) -> bool:
    """Check if a scan is due for the given source type."""
    last_scan = get_last_scan_time(source_type)
    if last_scan is None:
        return True
    return (time.time() - last_scan) >= SCAN_INTERVAL_SECONDS
