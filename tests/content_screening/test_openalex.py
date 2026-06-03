"""Tests for the OpenAlex discovery source (no network — `_get` is mocked)."""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from content_screening.models import Article, SourceType
from content_screening.openalex import (
    DiscoveryConfig,
    _is_future_date,
    _short_id,
    _work_to_article,
    fetch_openalex_articles,
    reconstruct_abstract,
)


# --- abstract reconstruction ------------------------------------------------


class TestReconstructAbstract:
    def test_round_trips_inverted_index(self):
        inv = {"Hello": [0], "world": [1], "again": [2, 4], "hello": [3]}
        assert reconstruct_abstract(inv) == "Hello world again hello again"

    def test_none_and_empty(self):
        assert reconstruct_abstract(None) is None
        assert reconstruct_abstract({}) is None

    def test_orders_by_position(self):
        inv = {"second": [1], "first": [0], "third": [2]}
        assert reconstruct_abstract(inv) == "first second third"


# --- small helpers ----------------------------------------------------------


class TestHelpers:
    def test_short_id(self):
        assert _short_id("https://openalex.org/W123") == "W123"
        assert _short_id("https://openalex.org/W123/") == "W123"
        assert _short_id(None) is None

    def test_future_date_guard(self):
        future = (date.today() + timedelta(days=30)).isoformat()
        past = (date.today() - timedelta(days=1)).isoformat()
        assert _is_future_date(future) is True
        assert _is_future_date(past) is False
        assert _is_future_date(None) is False
        assert _is_future_date("not-a-date") is False


# --- work -> Article mapping ------------------------------------------------


def _sample_work(**overrides) -> dict:
    work = {
        "id": "https://openalex.org/W42",
        "doi": "https://doi.org/10.1234/ABC.def",
        "title": "A study of <em>adverse</em> drug reactions",
        "publication_date": (date.today() - timedelta(days=2)).isoformat(),
        "abstract_inverted_index": {"Signal": [0], "detection": [1]},
        "authorships": [
            {
                "author_position": "first",
                "author": {
                    "id": "https://openalex.org/A5",
                    "display_name": "Marie Lindquist",
                    "orcid": "https://orcid.org/0000-0001-0001-0001",
                },
                "institutions": [
                    {"id": "https://openalex.org/I111684115", "display_name": "Uppsala Monitoring Centre"}
                ],
            },
            {
                "author_position": "last",
                "author": {"id": "https://openalex.org/A6", "display_name": "I. Ralph Edwards"},
                "institutions": [],
            },
        ],
        "primary_location": {
            "landing_page_url": "https://example.org/article/42",
            "source": {"display_name": "Drug Safety"},
        },
        "topics": [{"id": "https://openalex.org/T11943", "display_name": "Pharmacovigilance"}],
    }
    work.update(overrides)
    return work


class TestWorkToArticle:
    def test_maps_core_fields(self):
        art = _work_to_article(_sample_work(), ["topic"])
        assert art is not None
        assert art.external_id == "W42"
        assert art.source_type == SourceType.OPENALEX
        # DOI normalized: lowercase, no https://doi.org/ prefix.
        assert art.doi == "10.1234/abc.def"
        assert art.abstract == "Signal detection"
        assert art.authors == ["Marie Lindquist", "I. Ralph Edwards"]
        assert art.surfaced_by == ["topic"]
        assert art.categories == ["Pharmacovigilance"]
        # Keyword net still annotates (title contains "adverse").
        assert "adverse" in art.keywords_matched
        assert art.url == "https://example.org/article/42"

    def test_metadata_carries_affiliations_and_positions(self):
        art = _work_to_article(_sample_work(), ["institution"])
        rich = art.metadata["authorships"]
        assert rich[0]["position"] == "first"
        assert rich[0]["author_id"] == "A5"
        assert rich[0]["institutions"] == ["Uppsala Monitoring Centre"]
        assert art.metadata["venue"] == "Drug Safety"
        assert art.metadata["topic_ids"] == ["T11943"]

    def test_future_date_dropped(self):
        future = (date.today() + timedelta(days=10)).isoformat()
        assert _work_to_article(_sample_work(publication_date=future), ["topic"]) is None

    def test_missing_title_dropped(self):
        assert _work_to_article(_sample_work(title=""), ["topic"]) is None

    def test_url_falls_back_to_doi_then_id(self):
        art = _work_to_article(_sample_work(primary_location={}), ["topic"])
        assert art.url == "https://doi.org/10.1234/abc.def"
        art2 = _work_to_article(_sample_work(primary_location={}, doi=None), ["topic"])
        assert art2.url == "https://openalex.org/W42"


# --- fetch orchestration (mock the HTTP seam) -------------------------------


def _page(results):
    return {"results": results, "meta": {"next_cursor": None}}


class TestFetchOpenalexArticles:
    def test_topic_filter_and_mapping(self):
        cfg = DiscoveryConfig(topics=[{"id": "T11943", "name": "PV"}])

        captured = {}

        def fake_get(path, params, mailto):
            captured["path"] = path
            captured["filter"] = params["filter"]
            return _page([_sample_work()])

        with patch("content_screening.openalex._get", side_effect=fake_get):
            articles = fetch_openalex_articles(cfg)

        assert captured["path"] == "works"
        assert "topics.id:T11943" in captured["filter"]
        assert "from_publication_date:" in captured["filter"]
        assert len(articles) == 1
        assert articles[0].surfaced_by == ["topic"]

    def test_merges_surfaced_by_across_signals(self):
        # Same work id returned by both the topic and author signals.
        cfg = DiscoveryConfig(
            topics=[{"id": "T11943", "name": "PV"}],
            monitored_authors=["A5"],
        )

        def fake_get(path, params, mailto):
            return _page([_sample_work()])

        with patch("content_screening.openalex._get", side_effect=fake_get):
            articles = fetch_openalex_articles(cfg)

        assert len(articles) == 1
        assert set(articles[0].surfaced_by) == {"topic", "author"}

    def test_author_watchlist_splits_ids_and_orcids(self):
        cfg = DiscoveryConfig(
            monitored_authors=["A5", "0000-0001-0001-0001"],
        )
        filters = []

        def fake_get(path, params, mailto):
            filters.append(params["filter"])
            return _page([])

        with patch("content_screening.openalex._get", side_effect=fake_get):
            fetch_openalex_articles(cfg)

        assert any("authorships.author.id:A5" in f for f in filters)
        assert any("authorships.author.orcid:0000-0001-0001-0001" in f for f in filters)

    def test_institution_resolves_first_last_then_cites(self):
        cfg = DiscoveryConfig(
            institutions=[
                {"id": "I111684115", "name": "UMC", "author_positions": ["first", "last"]}
            ]
        )
        seed_work = {
            "id": "https://openalex.org/W100",
            "authorships": [
                {
                    "author_position": "first",
                    "institutions": [{"id": "https://openalex.org/I111684115"}],
                }
            ],
        }
        middle_only = {
            "id": "https://openalex.org/W200",
            "authorships": [
                {
                    "author_position": "middle",
                    "institutions": [{"id": "https://openalex.org/I111684115"}],
                }
            ],
        }
        calls = []

        def fake_get(path, params, mailto):
            calls.append(params["filter"])
            f = params["filter"]
            if f.startswith("authorships.institutions.id:"):
                return _page([seed_work, middle_only])
            if f.startswith("cites:"):
                return _page([_sample_work()])
            return _page([])

        with patch("content_screening.openalex._get", side_effect=fake_get):
            articles = fetch_openalex_articles(cfg)

        # Only the first-author seed work (W100) becomes a cites: seed, not W200.
        assert any(f == "cites:W100,from_publication_date:" + _today_window() for f in calls)
        assert all("W200" not in f for f in calls if f.startswith("cites:"))
        assert len(articles) == 1
        assert articles[0].surfaced_by == ["institution"]


def _today_window():
    from content_screening.constants import SCAN_LOOKBACK_DAYS

    return (date.today() - timedelta(days=SCAN_LOOKBACK_DAYS)).isoformat()
