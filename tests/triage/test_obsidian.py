"""Tests for the Obsidian stub writer and decision routing (build step 6)."""

import time
from datetime import datetime, timezone

import yaml

from content_screening.orm_models import ArticleORM
from triage import obsidian, routing
from triage.config import Settings


def make_paper(**overrides) -> ArticleORM:
    defaults = dict(
        id=1,
        external_id="2401.00001",
        source_type="arxiv",
        title="A Great Paper, About Things!",
        url="https://arxiv.org/abs/2401.00001",
        abstract="An abstract.",
        authors=["Ada Lovelace", "Alan Turing"],
        categories=["cs.LG"],
        keywords_matched=[],
        discovered_at=int(time.time()),
        llm_interest_score=0.6,
        llm_reasoning="Directly relevant to signal detection.",
        llm_tags=["signal-detection"],
        suggested_depth="deep",
        status="deep",
        decided_at=datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc).isoformat(),
        zotero_key=None,
        zotero_error=None,
        obsidian_path=None,
        obsidian_error=None,
        routing_attempts=0,
        next_retry_at=None,
    )
    defaults.update(overrides)
    return ArticleORM(**defaults)


def parse_frontmatter(text: str) -> dict:
    _, fm, _ = text.split("---", 2)
    return yaml.safe_load(fm)


def test_slugify_basic():
    assert obsidian.slugify("Hello, World! A Test") == "hello-world-a-test"


def test_slugify_truncates_to_60_no_trailing_hyphen():
    slug = obsidian.slugify("word " * 40)
    assert len(slug) <= 60
    assert not slug.endswith("-")


def test_write_stub_path_and_frontmatter(tmp_path):
    rel = obsidian.write_stub(tmp_path, make_paper())
    assert rel == "literature/inbox/2026-05-31-a-great-paper-about-things.md"

    content = (tmp_path / rel).read_text()
    fm = parse_frontmatter(content)
    assert fm["title"] == "A Great Paper, About Things!"
    assert fm["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert fm["status"] == "to-read"  # 'deep' -> to-read
    assert fm["tags"] == ["paper", "triage/deep"]
    assert fm["zotero"] == ""
    assert "Why this surfaced:" in content
    assert "signal detection" in content


def test_filed_status_maps_to_filed(tmp_path):
    rel = obsidian.write_stub(tmp_path, make_paper(status="filed"))
    fm = parse_frontmatter((tmp_path / rel).read_text())
    assert fm["status"] == "filed"
    assert fm["tags"] == ["paper", "triage/filed"]


def test_collision_gets_suffix(tmp_path):
    p = make_paper()
    first = obsidian.write_stub(tmp_path, p)
    second = obsidian.write_stub(tmp_path, p)
    assert first.endswith("-about-things.md")
    assert second.endswith("-about-things-2.md")


def test_route_decision_writes_and_is_idempotent(tmp_path):
    settings = Settings(obsidian_vault=str(tmp_path))
    paper = make_paper()

    routing.route_decision(paper, settings)
    assert paper.obsidian_path is not None
    assert paper.obsidian_error is None
    first_path = paper.obsidian_path
    assert (tmp_path / first_path).exists()

    # Second call must not rewrite or create a duplicate.
    routing.route_decision(paper, settings)
    assert paper.obsidian_path == first_path
    inbox = tmp_path / "literature" / "inbox"
    assert len(list(inbox.glob("*.md"))) == 1


def test_dismissed_has_no_side_effects(tmp_path):
    settings = Settings(obsidian_vault=str(tmp_path))
    paper = make_paper(status="dismissed")
    routing.route_decision(paper, settings)
    assert paper.obsidian_path is None
    assert not (tmp_path / "literature").exists()


def test_unconfigured_vault_is_a_noop():
    settings = Settings(obsidian_vault="")
    paper = make_paper()
    routing.route_decision(paper, settings)
    assert paper.obsidian_path is None
    assert paper.obsidian_error is None
