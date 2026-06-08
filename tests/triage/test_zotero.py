"""Tests for the Zotero pusher and `kept` decision routing (build step 7).

``pyzotero`` and the GCP secret fetch are mocked throughout — no network or
credentials are touched.
"""

import pytest

from triage import routing, zotero
from triage.config import Settings

from tests.triage.test_obsidian import make_paper


class FakeZot:
    """Stand-in for a ``pyzotero.zotero.Zotero`` client."""

    def __init__(self, create_response=None, raise_on_create=None):
        self.create_response = create_response or {
            "successful": {"0": {"key": "ABCD1234"}},
            "failed": {},
        }
        self.raise_on_create = raise_on_create
        self.created_items = None

    def item_template(self, item_type):
        self.requested_type = item_type
        # A minimal preprint-ish template, including the fields the pusher fills.
        return {
            "itemType": item_type,
            "title": "",
            "creators": [],
            "abstractNote": "",
            "url": "",
            "archiveID": "",
            "tags": [],
        }

    def create_items(self, items):
        if self.raise_on_create:
            raise self.raise_on_create
        self.created_items = items
        return self.create_response


@pytest.fixture
def fake_zot(monkeypatch):
    zot = FakeZot()
    monkeypatch.setattr(zotero, "_client", lambda: zot)
    return zot


def test_item_type_mapping():
    assert zotero._item_type("arxiv") == "preprint"
    assert zotero._item_type("rss") == "journalArticle"


def test_creators_splits_names_and_handles_single_token():
    creators = zotero._creators(["Ada Lovelace", "CERN", "  "])
    assert creators[0] == {
        "creatorType": "author",
        "firstName": "Ada",
        "lastName": "Lovelace",
    }
    assert creators[1] == {"creatorType": "author", "name": "CERN"}
    assert len(creators) == 2  # blank entries dropped


def test_push_paper_builds_template_and_returns_key(fake_zot):
    key = zotero.push_paper(make_paper())

    assert key == "ABCD1234"
    assert fake_zot.requested_type == "preprint"
    item = fake_zot.created_items[0]
    assert item["title"] == "A Great Paper, About Things!"
    assert item["abstractNote"] == "An abstract."
    assert item["url"] == "https://arxiv.org/abs/2401.00001"
    assert item["tags"] == [{"tag": "triage/kept"}]
    assert item["archiveID"] == "2401.00001"
    assert {"creatorType": "author", "firstName": "Alan", "lastName": "Turing"} in item[
        "creators"
    ]


def test_push_paper_raises_on_failed_response(monkeypatch):
    zot = FakeZot(create_response={"successful": {}, "failed": {"0": "bad data"}})
    monkeypatch.setattr(zotero, "_client", lambda: zot)
    with pytest.raises(RuntimeError, match="rejected"):
        zotero.push_paper(make_paper())


def test_route_deep_pushes_zotero_and_is_idempotent(fake_zot):
    settings = Settings(zotero_enabled=True)  # no obsidian vault
    paper = make_paper(status="deep")

    routing.route_decision(paper, settings)
    assert paper.zotero_key == "ABCD1234"
    assert paper.zotero_error is None

    # Second call must not push again (idempotent via existing zotero_key).
    fake_zot.created_items = None
    routing.route_decision(paper, settings)
    assert fake_zot.created_items is None


def test_route_filed_does_not_push_to_zotero(fake_zot):
    settings = Settings(zotero_enabled=True)
    paper = make_paper(status="filed")
    routing.route_decision(paper, settings)
    assert paper.zotero_key is None
    assert fake_zot.created_items is None


def test_route_zotero_unconfigured_is_noop(fake_zot):
    settings = Settings(zotero_enabled=False)
    paper = make_paper(status="deep")
    routing.route_decision(paper, settings)
    assert paper.zotero_key is None
    assert fake_zot.created_items is None


def test_route_records_error_without_raising(monkeypatch):
    zot = FakeZot(raise_on_create=RuntimeError("network down"))
    monkeypatch.setattr(zotero, "_client", lambda: zot)
    paper = make_paper(status="deep")

    routing.route_decision(paper, Settings(zotero_enabled=True))

    assert paper.zotero_key is None
    assert "network down" in paper.zotero_error
