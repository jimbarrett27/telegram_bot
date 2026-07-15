"""Pick each day's tapestry model by random-sampling OpenRouter's best SVG models.

Rather than hard-coding one model, every day is drawn by a model chosen at
random from the current top of OpenRouter's "design arena" *SVG* leaderboard
(fetched live, so the pool self-updates as models rise and fall). The choice is
seeded by the date, so a given day always maps to the same model -- backfills
are reproducible and the model recorded in the panel JSON is exactly the one
that ran.

If the leaderboard can't be fetched, we fall back to a small hard-coded pool so
the daily job degrades gracefully instead of failing.
"""

import json
import logging
import random
import urllib.request

logger = logging.getLogger(__name__)

MODELS_URL = "https://openrouter.ai/api/v1/models"
TOP_N = 15
FETCH_TIMEOUT = 15  # seconds

# Snapshot of strong SVG models, used only when the live leaderboard is
# unreachable. Kept short and current-ish; the live list is preferred.
FALLBACK_MODELS = (
    "google/gemini-3.1-pro-preview",
    "anthropic/claude-opus-4.8",
    "anthropic/claude-sonnet-5",
    "openai/gpt-5.1",
    "deepseek/deepseek-v4-pro",
)


def _svg_elo(model: dict) -> float | None:
    """Return a model's design-arena SVG Elo, or ``None`` if it isn't ranked."""
    benchmarks = model.get("benchmarks") or {}
    for row in benchmarks.get("design_arena") or []:
        if row.get("arena") == "models" and row.get("category") == "svg":
            return row.get("elo")
    return None


def top_svg_models(limit: int = TOP_N) -> list[str]:
    """Return the ids of the top ``limit`` models by design-arena SVG Elo.

    Falls back to :data:`FALLBACK_MODELS` if the leaderboard can't be fetched or
    contains no SVG-ranked models.
    """
    try:
        with urllib.request.urlopen(MODELS_URL, timeout=FETCH_TIMEOUT) as resp:
            data = json.load(resp)["data"]
    except Exception:
        logger.exception("Failed to fetch OpenRouter models; using fallback pool")
        return list(FALLBACK_MODELS)

    ranked = sorted(
        ((elo, m["id"]) for m in data if (elo := _svg_elo(m)) is not None),
        reverse=True,
    )
    top = [model_id for _, model_id in ranked[:limit]]
    if not top:
        logger.warning("No SVG-ranked models in leaderboard; using fallback pool")
        return list(FALLBACK_MODELS)
    return top


def pick_model(day: str, limit: int = TOP_N) -> str:
    """Deterministically pick one of the top SVG models for ``day`` (YYYY-MM-DD).

    Seeded by ``day`` so the same date always yields the same model, given the
    same leaderboard.
    """
    pool = top_svg_models(limit)
    model = random.Random(day).choice(pool)
    logger.info("Selected model %s for %s (from a pool of %d)", model, day, len(pool))
    return model
