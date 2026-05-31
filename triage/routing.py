"""Routes triage decisions into external tools (Obsidian now, Zotero in step 7).

Side effects mutate the paper row in place (``obsidian_path``/``obsidian_error``,
later ``zotero_key``/``zotero_error``); the caller persists them. Failures are
recorded on the row rather than raised, so a decision always succeeds even if
routing doesn't — matching the spec's best-effort tolerance.
"""

from pathlib import Path

from content_screening.orm_models import ArticleORM
from triage import obsidian
from triage.config import Settings
from util.logging_util import setup_logger

logger = setup_logger(__name__)

# Decisions that produce an Obsidian stub.
_OBSIDIAN_DECISIONS = {"deep", "filed"}


def route_decision(paper: ArticleORM, settings: Settings) -> None:
    """Perform the external side effects for a freshly-decided paper."""
    if paper.status in _OBSIDIAN_DECISIONS:
        _route_obsidian(paper, settings)
    # `dismissed` has no side effects. Zotero push for `deep` is added in step 7.


def _route_obsidian(paper: ArticleORM, settings: Settings) -> None:
    if not settings.obsidian_vault:
        logger.info("Obsidian vault not configured; skipping stub for paper %s", paper.id)
        return

    vault = Path(settings.obsidian_vault)
    # Idempotency: if we've already written this paper's stub and it still
    # exists, do nothing (safe to call repeatedly, e.g. from the retry loop).
    if paper.obsidian_path and (vault / paper.obsidian_path).exists():
        return

    try:
        rel_path = obsidian.write_stub(vault, paper, settings.obsidian_inbox_subdir)
        paper.obsidian_path = rel_path
        paper.obsidian_error = None
        logger.info("wrote Obsidian stub for paper %s: %s", paper.id, rel_path)
    except Exception as exc:  # noqa: BLE001 - record any failure on the row
        paper.obsidian_error = str(exc)
        logger.error("Obsidian write failed for paper %s: %s", paper.id, exc)
