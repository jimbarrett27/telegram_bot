"""Background retry loop for failed paper routing (build step 8).

When a Zotero/Obsidian push fails, ``routing.route_and_schedule`` records the
error and stamps ``next_retry_at``. This module periodically re-attempts every
paper whose backoff timer has elapsed, until routing completes or the attempt
cap is hit. The loop runs inside the FastAPI process (started by the app's
lifespan) and does its blocking DB/network work in a worker thread so the event
loop stays responsive.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from content_screening.db_engine import get_session
from content_screening.orm_models import ArticleORM
from triage import routing
from triage.config import Settings
from util.logging_util import setup_logger

logger = setup_logger(__name__)


def due_for_retry(session: Session, now_iso: str) -> list[ArticleORM]:
    """Papers whose ``next_retry_at`` is set and has elapsed.

    ``next_retry_at`` is a UTC ISO-8601 string, so a lexical ``<=`` compare is
    chronologically correct as long as every value uses the same format (they
    all come from ``datetime.now(timezone.utc).isoformat()``).
    """
    stmt = select(ArticleORM).where(
        ArticleORM.next_retry_at.is_not(None),
        ArticleORM.next_retry_at <= now_iso,
    )
    return list(session.scalars(stmt))


def run_retry_pass(settings: Settings) -> int:
    """Re-attempt routing for all due papers. Returns how many were processed."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_session() as session:
        papers = due_for_retry(session, now_iso)
        for paper in papers:
            routing.route_and_schedule(paper, settings)
            logger.info(
                "routing retry: paper=%s attempt=%d complete=%s",
                paper.id,
                paper.routing_attempts,
                routing.is_routing_complete(paper, settings),
            )
        return len(papers)


async def retry_loop(settings: Settings) -> None:
    """Scan for due retries forever, sleeping between passes. Cancel-safe."""
    logger.info(
        "routing retry loop started (every %ds)",
        settings.routing_retry_interval_seconds,
    )
    while True:
        await asyncio.sleep(settings.routing_retry_interval_seconds)
        try:
            await asyncio.to_thread(run_retry_pass, settings)
        except Exception:  # noqa: BLE001 - a bad pass must not kill the loop
            logger.exception("routing retry pass failed")
