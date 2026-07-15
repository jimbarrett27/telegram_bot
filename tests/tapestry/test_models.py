"""Tests for per-day model selection (ranking + deterministic pick, no network)."""

import json
import io

import pytest

from tapestry import models


def _model(model_id, svg_elo=None):
    """Build a minimal OpenRouter model entry, optionally SVG-ranked."""
    entry = {"id": model_id, "benchmarks": {}}
    if svg_elo is not None:
        entry["benchmarks"]["design_arena"] = [
            {"arena": "models", "category": "svg", "elo": svg_elo},
            # a non-svg row that must be ignored by the ranker
            {"arena": "models", "category": "3d", "elo": 9999},
        ]
    return entry


SAMPLE = {
    "data": [
        _model("a/top", svg_elo=1400),
        _model("b/mid", svg_elo=1200),
        _model("c/low", svg_elo=1000),
        _model("d/unranked"),  # no svg score -> excluded
    ]
}


@pytest.fixture
def fake_leaderboard(monkeypatch):
    def fake_urlopen(url, timeout=None):
        return io.BytesIO(json.dumps(SAMPLE).encode())

    monkeypatch.setattr(models.urllib.request, "urlopen", fake_urlopen)


def test_top_svg_models_ranks_and_excludes_unranked(fake_leaderboard):
    assert models.top_svg_models() == ["a/top", "b/mid", "c/low"]


def test_top_svg_models_respects_limit(fake_leaderboard):
    assert models.top_svg_models(limit=2) == ["a/top", "b/mid"]


def test_pick_model_is_deterministic_per_day(fake_leaderboard):
    first = models.pick_model("2026-07-14")
    assert first == models.pick_model("2026-07-14")
    assert first in {"a/top", "b/mid", "c/low"}


def test_pick_model_varies_across_days(fake_leaderboard):
    picks = {models.pick_model(f"2026-07-{d:02d}") for d in range(1, 29)}
    assert len(picks) > 1  # not stuck on a single model


def test_falls_back_when_fetch_fails(monkeypatch):
    def boom(url, timeout=None):
        raise OSError("network down")

    monkeypatch.setattr(models.urllib.request, "urlopen", boom)
    assert models.top_svg_models() == list(models.FALLBACK_MODELS)
    assert models.pick_model("2026-07-14") in models.FALLBACK_MODELS
