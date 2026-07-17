"""Generate a Bayeux-style "news tapestry" from news stories via OpenRouter.

Each panel covers three stories; consecutive panels are stitched together with a
vertical overlap so the tapestry grows into one continuous image. The OpenRouter
key is fetched securely by the house LLM helper, so nothing secret lives here.
"""

import logging
from pathlib import Path
from typing import NamedTuple

from llm.llm_util import get_llm_response
from tapestry.svg import (
    OVERLAP,
    PANEL_HEIGHT,
    PANEL_WIDTH,
    extract_panel,
    stitch_svgs,
    svg_problems,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "deepseek/deepseek-v4-pro"
STORIES_PER_PANEL = 3
MAX_ATTEMPTS = 3
PROMPT_TEMPLATE = str(Path(__file__).parent / "prompts" / "tapestry_panel.jinja2")


class Panel(NamedTuple):
    """A generated panel: its SVG markup and the model's stated plan (if any)."""

    svg: str
    plan: str | None


def generate_panel(
    stories,
    previous_svg: str = None,
    model: str = DEFAULT_MODEL,
    max_attempts: int = MAX_ATTEMPTS,
) -> Panel:
    """Generate one tapestry panel from (at least) three stories.

    ``stories`` is a sequence of dicts with ``title``, ``summary`` and ``link``
    keys. Pass ``previous_svg`` to ask the model to visually continue from
    yesterday's panel.

    The model's output is structurally validated (see
    :func:`tapestry.svg.svg_problems`); if a panel is malformed the same model is
    retried up to ``max_attempts`` times, with the problem fed back into the
    prompt so the retry knows what to fix, before giving up with a
    ``RuntimeError``. Returns a :class:`Panel` with the cleaned SVG and the
    model's plan.
    """
    params = {
        "stories": [dict(s) for s in stories[:STORIES_PER_PANEL]],
        "previous_svg": previous_svg,
        "panel_width": PANEL_WIDTH,
        "panel_height": PANEL_HEIGHT,
        "overlap": OVERLAP,
    }

    last_problem = None
    for attempt in range(1, max_attempts + 1):
        content = get_llm_response(
            PROMPT_TEMPLATE, {**params, "problem": last_problem}, model
        )
        try:
            svg, plan = extract_panel(content)
            problems = svg_problems(svg)
        except ValueError as exc:
            problems = [str(exc)]

        if not problems:
            return Panel(svg=svg, plan=plan)

        last_problem = "; ".join(problems)
        logger.warning(
            "Panel attempt %d/%d with %s produced an invalid SVG: %s",
            attempt, max_attempts, model, last_problem,
        )

    raise RuntimeError(
        f"Failed to generate a valid SVG with {model} after {max_attempts} "
        f"attempts (last problem: {last_problem})"
    )


def generate_tapestry(stories, days: int = None, model: str = DEFAULT_MODEL) -> str:
    """Generate one panel per group of three stories and stitch them together.

    ``days`` caps how many panels to generate; defaults to as many complete
    groups of three as ``stories`` allows. Each panel after the first is asked
    to continue seamlessly from the previous one.
    """
    groups = [
        stories[i:i + STORIES_PER_PANEL]
        for i in range(0, len(stories) - (STORIES_PER_PANEL - 1), STORIES_PER_PANEL)
    ]
    if days is not None:
        groups = groups[:days]

    svgs = []
    previous_svg = None
    for group in groups:
        panel = generate_panel(group, previous_svg=previous_svg, model=model)
        svgs.append(panel.svg)
        previous_svg = panel.svg
        logger.info("Generated tapestry panel %d/%d", len(svgs), len(groups))

    return stitch_svgs(svgs)
