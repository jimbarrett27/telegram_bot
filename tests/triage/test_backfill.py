"""Tests for triage.backfill — candidate selection and reset/route behaviour.

The real Zotero/Obsidian calls are monkeypatched.  Uses an in-memory SQLite DB
wired through ``db_engine.set_engine``, following the same pattern as
``test_retry.py``.
"""

import time

import pytest
from sqlalchemy import create_engine

from content_screening import db_engine
from content_screening.orm_models import ArticleORM, Base
from triage import backfill, routing
from triage.config import Settings

# Settings with Zotero enabled so ``is_routing_complete`` treats a missing
# ``zotero_key`` as incomplete.
ZOTERO_ON = dict(zotero_enabled=True, obsidian_vault="")


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db_engine.set_engine(engine)
    yield engine
    db_engine.reset_engine()


def _make_orm(
    external_id: str,
    status: str,
    zotero_key: str | None = None,
    routing_attempts: int = 0,
    zotero_error: str | None = None,
    next_retry_at: str | None = None,
) -> ArticleORM:
    return ArticleORM(
        external_id=external_id,
        source_type="arxiv",
        title=f"Paper {external_id}",
        url=f"https://arxiv.org/abs/{external_id}",
        discovered_at=int(time.time()),
        status=status,
        routing_attempts=routing_attempts,
        zotero_key=zotero_key,
        zotero_error=zotero_error,
        next_retry_at=next_retry_at,
    )


class TestSelectIncompletePapers:
    """_select_incomplete_kept returns exactly the right subset."""

    def test_selects_kept_without_zotero_key(self, memory_db):
        settings = Settings(**ZOTERO_ON)
        with db_engine.get_session() as session:
            session.add(_make_orm("target", "kept", zotero_key=None))

        with db_engine.get_session() as session:
            result = backfill._select_incomplete_kept(session, settings)
            # Read attributes while still inside the session to avoid
            # DetachedInstanceError after the context manager closes.
            ids = [r.external_id for r in result]

        assert len(ids) == 1
        assert ids[0] == "target"

    def test_skips_kept_paper_already_complete(self, memory_db):
        settings = Settings(**ZOTERO_ON)
        with db_engine.get_session() as session:
            # zotero_key already set → routing complete
            session.add(_make_orm("done", "kept", zotero_key="ZKEY123"))

        with db_engine.get_session() as session:
            result = backfill._select_incomplete_kept(session, settings)

        assert result == []

    def test_skips_dismissed_paper(self, memory_db):
        settings = Settings(**ZOTERO_ON)
        with db_engine.get_session() as session:
            session.add(_make_orm("dis", "dismissed"))

        with db_engine.get_session() as session:
            result = backfill._select_incomplete_kept(session, settings)

        assert result == []

    def test_skips_pending_paper(self, memory_db):
        settings = Settings(**ZOTERO_ON)
        with db_engine.get_session() as session:
            session.add(_make_orm("pend", "pending"))

        with db_engine.get_session() as session:
            result = backfill._select_incomplete_kept(session, settings)

        assert result == []

    def test_mixed_rows_only_incomplete_kept_returned(self, memory_db):
        settings = Settings(**ZOTERO_ON)
        with db_engine.get_session() as session:
            session.add(_make_orm("t1", "kept", zotero_key=None))   # target
            session.add(_make_orm("t2", "kept", zotero_key="K"))    # already done
            session.add(_make_orm("t3", "dismissed"))               # wrong status
            session.add(_make_orm("t4", "pending"))                 # wrong status

        with db_engine.get_session() as session:
            result = backfill._select_incomplete_kept(session, settings)
            ids = [r.external_id for r in result]

        assert ids == ["t1"]


class TestMainFlow:
    """main() resets bookkeeping and calls route_and_schedule for each target."""

    def test_main_routes_incomplete_kept_paper(self, memory_db, monkeypatch):
        """main() calls route_and_schedule exactly once for the incomplete paper
        and sets a fake zotero_key so the paper shows up in the pushed count."""
        # Seed: one incomplete kept, one complete kept, one dismissed.
        with db_engine.get_session() as session:
            session.add(_make_orm("k-incomplete", "kept", zotero_key=None,
                                  routing_attempts=3, zotero_error="old error",
                                  next_retry_at="2099-01-01T00:00:00+00:00"))
            session.add(_make_orm("k-done", "kept", zotero_key="EXISTS"))
            session.add(_make_orm("dis", "dismissed"))

        routed: list[int] = []

        def fake_route_and_schedule(paper, _settings):
            routed.append(paper.id)
            paper.zotero_key = "FAKE_KEY"

        monkeypatch.setattr(routing, "route_and_schedule", fake_route_and_schedule)
        monkeypatch.setattr(backfill, "get_settings", lambda: Settings(**ZOTERO_ON))

        backfill.main()

        # Only the incomplete kept paper was routed.
        assert len(routed) == 1

        # Verify bookkeeping was reset before routing was called.
        with db_engine.get_session() as session:
            from sqlalchemy import select
            paper = session.scalar(
                select(ArticleORM).where(ArticleORM.external_id == "k-incomplete")
            )
            assert paper.zotero_key == "FAKE_KEY"
            assert paper.zotero_error is None
            assert paper.next_retry_at is None

    def test_main_is_noop_when_all_complete(self, memory_db, monkeypatch, capsys):
        """A second run with all papers already complete prints 0 candidates."""
        with db_engine.get_session() as session:
            session.add(_make_orm("k-done", "kept", zotero_key="KEY"))

        routed: list[int] = []
        monkeypatch.setattr(
            routing, "route_and_schedule", lambda p, _s: routed.append(p.id)
        )
        monkeypatch.setattr(backfill, "get_settings", lambda: Settings(**ZOTERO_ON))

        backfill.main()

        assert routed == []
        captured = capsys.readouterr()
        assert "0 kept paper" in captured.out
