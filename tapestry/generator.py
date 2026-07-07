"""Generate a Bayeux-style "news tapestry" from news stories via OpenRouter.

Each panel covers three stories; consecutive panels are stitched together with a
vertical overlap so the tapestry grows into one continuous image. The OpenRouter
key is fetched securely by the house LLM helper, so nothing secret lives here.
"""

import logging
from pathlib import Path

from llm.llm_util import get_llm_response
from tapestry.svg import PANEL_HEIGHT, PANEL_WIDTH, extract_svg, stitch_svgs

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "deepseek/deepseek-v4-pro"
STORIES_PER_PANEL = 3
PROMPT_TEMPLATE = str(Path(__file__).parent / "prompts" / "tapestry_panel.jinja2")


def generate_panel(stories, previous_svg: str = None, model: str = DEFAULT_MODEL) -> str:
    """Generate one tapestry panel from (at least) three stories.

    ``stories`` is a sequence of dicts with ``title``, ``summary`` and ``link``
    keys. Pass ``previous_svg`` to ask the model to visually continue from
    yesterday's panel.
    """
    params = {
        "stories": [dict(s) for s in stories[:STORIES_PER_PANEL]],
        "previous_svg": previous_svg,
        "panel_width": PANEL_WIDTH,
        "panel_height": PANEL_HEIGHT,
    }
    content = get_llm_response(PROMPT_TEMPLATE, params, model)
    return extract_svg(content)


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
        svg = generate_panel(group, previous_svg=previous_svg, model=model)
        svgs.append(svg)
        previous_svg = svg
        logger.info("Generated tapestry panel %d/%d", len(svgs), len(groups))

    return stitch_svgs(svgs)
