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
from tapestry.generator import DEFAULT_MODEL, PROMPT_TEMPLATE, generate_panel

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main(model: str = DEFAULT_MODEL) -> None:
    index = storage.read_index()
    if not index or not index["dates"]:
        print("No panels to backfill")
        return

    dates = sorted(index["dates"])  # oldest first: the order the seams join in
    prompt_template = Path(PROMPT_TEMPLATE).read_text()
    previous_svg = None

    for date in dates:
        stories = storage.read_panel(date)["stories"]
        svg = generate_panel(stories, previous_svg=previous_svg, model=model)
        storage.write_panel({
            "date": date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "prompt_template": prompt_template,
            "stories": stories,
            "svg": svg,
        })
        previous_svg = svg
        print(f"Regenerated panel for {date}")

    print(f"Backfill complete: {len(dates)} panel(s)")


if __name__ == "__main__":
    main()
