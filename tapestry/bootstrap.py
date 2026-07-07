"""One-off: generate and upload the first tapestry panel.

Run once manually to seed day one; the daily scheduler (:func:`tapestry.daily.
daily_tapestry_task`) takes over from the next day. Safe to re-run -- it skips if
today's panel already exists.

    uv run python -m tapestry.bootstrap
"""

import logging

from tapestry.daily import generate_next_panel

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    day = generate_next_panel()
    if day:
        print(f"Seeded tapestry panel for {day}")
    else:
        print("Panel for today already exists; nothing to do")


if __name__ == "__main__":
    main()
