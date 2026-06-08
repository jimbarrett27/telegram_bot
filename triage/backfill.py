"""One-off Zotero backfill for ``kept`` papers that are not yet routing-complete.

Run with::

    uv run python -m triage.backfill

Selects every ``kept`` paper for which ``routing.is_routing_complete`` returns
``False``, resets the retry bookkeeping, and calls
``routing.route_and_schedule``.  The script is re-runnable: a second pass with
all papers already complete reports 0 candidates.

Needs Zotero + Obsidian enabled in the environment at run time — this is a
deploy-time orchestrator step, not executed during tests.
"""

from sqlalchemy import select

from content_screening.db_engine import get_session
from content_screening.orm_models import ArticleORM
from triage import routing
from triage.config import get_settings
from util.logging_util import setup_logger

logger = setup_logger(__name__)


def _select_incomplete_kept(session, settings) -> list[ArticleORM]:
    """Return every ``kept`` paper that is not yet routing-complete."""
    stmt = select(ArticleORM).where(ArticleORM.status == "kept")
    candidates = list(session.scalars(stmt))
    return [p for p in candidates if not routing.is_routing_complete(p, settings)]


def main() -> None:
    settings = get_settings()
    logger.info("backfill: starting Zotero backfill run")

    target_ids: list[int] = []
    with get_session() as session:
        targets = _select_incomplete_kept(session, settings)
        n_candidates = len(targets)
        # Collect IDs before routing so we can re-query after the session closes.
        target_ids = [p.id for p in targets]
        print(f"Backfill: {n_candidates} kept paper(s) not yet routing-complete.")

        for paper in targets:
            logger.info(
                "backfill: resetting paper id=%s title=%r", paper.id, paper.title
            )
            paper.routing_attempts = 0
            paper.zotero_error = None
            paper.next_retry_at = None
            routing.route_and_schedule(paper, settings)

        # session commits on context-manager exit (db_engine.get_session contract)

    # Re-open a fresh session to report final state, so the committed values are
    # read back and we don't mis-report based on in-memory ORM state.
    n_pushed = 0
    failure_lines: list[str] = []
    with get_session() as session:
        stmt = select(ArticleORM).where(
            ArticleORM.status == "kept",
            ArticleORM.id.in_(target_ids),
        )
        for paper in session.scalars(stmt):
            if paper.zotero_key:
                n_pushed += 1
            else:
                failure_lines.append(
                    f"    id={paper.id!r}  title={paper.title!r}"
                    f"  error={paper.zotero_error!r}"
                )

    n_failed = len(failure_lines)
    print(f"  pushed (have zotero_key): {n_pushed}")
    print(f"  still failed (no zotero_key): {n_failed}")
    if failure_lines:
        print("  Failures:")
        for line in failure_lines:
            print(line)

    logger.info(
        "backfill: done. candidates=%d pushed=%d failed=%d",
        n_candidates,
        n_pushed,
        n_failed,
    )


if __name__ == "__main__":
    main()
