"""One-off: regenerate every existing tapestry panel with the current prompt.

Re-runs the generator over the panels already in GCS, reusing each day's stored
stories so only the *artwork* changes (same news, new rendering). Panels are
regenerated oldest-first and each one after the first is given the freshly
regenerated previous panel as its ``previous_svg``, so the new seam rules
(transparent top overlap, interlocking foreground) actually take effect across
days.

Overwrites the stored panels in place. Safe to re-run. Needs the same GCP + LLM
credentials as the daily job:

    uv run python -m tapestry.backfill
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from tapestry import storage
from tapestry.generator import PROMPT_TEMPLATE, generate_panel
from tapestry.models import pick_model

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main(model: str | None = None) -> None:
    """Regenerate every stored panel's artwork, reusing each day's stories.

    ``model`` pins a single model for the whole run; by default each day gets its
    own per-day random pick (see :func:`tapestry.models.pick_model`), matching how
    the daily job now chooses. The model used and its plan are recorded per panel.
    """
    index = storage.read_index()
    if not index or not index["dates"]:
        print("No panels to backfill")
        return

    dates = sorted(index["dates"])  # oldest first: the order the seams join in
    prompt_template = Path(PROMPT_TEMPLATE).read_text()
    previous_svg = None

    for date in dates:
        stories = storage.read_panel(date)["stories"]
        day_model = model or pick_model(date)
        panel = generate_panel(stories, previous_svg=previous_svg, model=day_model)
        storage.write_panel({
            "date": date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": day_model,
            "plan": panel.plan,
            "prompt_template": prompt_template,
            "stories": stories,
            "svg": panel.svg,
        })
        previous_svg = panel.svg
        print(f"Regenerated panel for {date} with {day_model}")

    print(f"Backfill complete: {len(dates)} panel(s)")


if __name__ == "__main__":
    main()
