"""Tests for routing completeness, retry scheduling, and the retry pass (step 8).

The actual Zotero/Obsidian side effects are mocked — these cover the bookkeeping
(``is_routing_complete`` / ``route_and_schedule``) and the DB query that drives
the background loop.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine

from content_screening import db_engine
from content_screening.orm_models import ArticleORM
from triage import retry, routing
from triage.config import Settings

from tests.triage.test_obsidian import make_paper

BOTH_ON = dict(zotero_enabled=True, obsidian_vault="/tmp/vault")


def _past() -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()


def _future() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()


# --- is_routing_complete ------------------------------------------------------


def test_complete_requires_each_enabled_target():
    settings = Settings(**BOTH_ON)
    paper = make_paper(status="deep", zotero_key=None, obsidian_path=None)
    assert not routing.is_routing_complete(paper, settings)
    paper.zotero_key = "K"
    assert not routing.is_routing_complete(paper, settings)  # obsidian still missing
    paper.obsidian_path = "Papers/x.md"
    assert routing.is_routing_complete(paper, settings)


def test_complete_ignores_disabled_targets():
    # Both integrations off → nothing is outstanding even for a `deep` paper.
    settings = Settings(zotero_enabled=False, obsidian_vault="")
    paper = make_paper(status="deep", zotero_key=None, obsidian_path=None)
    assert routing.is_routing_complete(paper, settings)


def test_dismissed_is_always_complete():
    settings = Settings(**BOTH_ON)
    assert routing.is_routing_complete(make_paper(status="dismissed"), settings)


# --- route_and_schedule -------------------------------------------------------


def test_schedule_clears_retry_on_success(monkeypatch):
    settings = Settings(**BOTH_ON)
    paper = make_paper(status="deep")

    def fake_route(p, _s):
        p.zotero_key = "K"
        p.obsidian_path = "Papers/x.md"

    monkeypatch.setattr(routing, "route_decision", fake_route)
    routing.route_and_schedule(paper, settings)

    assert paper.routing_attempts == 0
    assert paper.next_retry_at is None


def test_schedule_sets_backoff_on_failure(monkeypatch):
    settings = Settings(**BOTH_ON, routing_max_attempts=6)
    paper = make_paper(status="deep")
    monkeypatch.setattr(
        routing,
        "route_decision",
        lambda p, _s: setattr(p, "zotero_error", "boom"),
    )
    routing.route_and_schedule(paper, settings)

    assert paper.routing_attempts == 1
    assert paper.next_retry_at is not None
    assert datetime.fromisoformat(paper.next_retry_at) > datetime.now(timezone.utc)


def test_schedule_gives_up_at_max(monkeypatch):
    settings = Settings(**BOTH_ON, routing_max_attempts=2)
    paper = make_paper(status="deep", routing_attempts=1)  # one prior attempt
    monkeypatch.setattr(routing, "route_decision", lambda p, _s: None)  # still fails
    routing.route_and_schedule(paper, settings)

    assert paper.routing_attempts == 2
    assert paper.next_retry_at is None  # gave up; error stays on the row


def test_backoff_grows_and_caps():
    settings = Settings(routing_retry_base_seconds=60)
    now = datetime.now(timezone.utc)
    first = datetime.fromisoformat(routing._next_retry_at(1, settings))
    capped = datetime.fromisoformat(routing._next_retry_at(20, settings))
    assert 55 <= (first - now).total_seconds() <= 65  # base * 2**0 = 60s
    assert (capped - now).total_seconds() <= routing._RETRY_CAP_SECONDS + 5


# --- run_retry_pass (DB-backed) ----------------------------------------------


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    ArticleORM.metadata.create_all(engine)
    db_engine.set_engine(engine)
    yield
    db_engine.reset_engine()


def test_run_retry_pass_processes_only_due_papers(memory_db, monkeypatch):
    with db_engine.get_session() as session:
        session.add(make_paper(id=1, external_id="due", status="deep", next_retry_at=_past()))
        session.add(make_paper(id=2, external_id="later", status="deep", next_retry_at=_future()))
        session.add(make_paper(id=3, external_id="done", status="deep", next_retry_at=None))

    seen: list[int] = []
    monkeypatch.setattr(routing, "route_and_schedule", lambda p, _s: seen.append(p.id))

    processed = retry.run_retry_pass(Settings(**BOTH_ON))

    assert processed == 1
    assert seen == [1]  # only the past-due paper
