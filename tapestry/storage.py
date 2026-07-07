"""GCS storage for the news tapestry: one JSON blob per daily panel plus a manifest.

The website (a separate, GCP-hosted repo) reads these public objects directly by
URL, so this layout *is* the website's contract:

    tapestry/index.json          -- manifest: geometry + the list of available dates
    tapestry/panels/<date>.json  -- one day: model, prompt template, the three
                                    stories (title/summary/link), and the panel SVG

Panels are stored per-day (a 1600x200 section), never as one growing stitched
image -- the website reassembles a window of panels client-side using the
geometry in the manifest. Objects are public-read, so no auth is needed to fetch
them from the browser.
"""

import json
import logging
from datetime import datetime, timezone

from google.cloud import storage

from tapestry.svg import OVERLAP, PANEL_HEIGHT, PANEL_WIDTH

logger = logging.getLogger(__name__)

PROJECT_ID = "personal-website-318015"
BUCKET_NAME = "personal-website-318015-tapestry"
INDEX_BLOB = "tapestry/index.json"
PANEL_BLOB = "tapestry/panels/{date}.json"


def _bucket():
    return storage.Client(project=PROJECT_ID).bucket(BUCKET_NAME)


def read_index() -> dict | None:
    """Return the manifest, or ``None`` if the tapestry hasn't been seeded yet."""
    blob = _bucket().blob(INDEX_BLOB)
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())


def read_panel(date: str) -> dict:
    """Return the stored panel dict (stories + svg) for ``date`` (YYYY-MM-DD)."""
    blob = _bucket().blob(PANEL_BLOB.format(date=date))
    return json.loads(blob.download_as_text())


def write_panel(panel: dict) -> None:
    """Upload one day's panel JSON, keyed by its ``date``."""
    blob = _bucket().blob(PANEL_BLOB.format(date=panel["date"]))
    blob.upload_from_string(json.dumps(panel), content_type="application/json")
    logger.info("Uploaded tapestry panel for %s (%d bytes)", panel["date"], len(panel["svg"]))


def update_index(date: str) -> None:
    """Append ``date`` to the manifest (creating it the first time)."""
    index = read_index() or {
        "geometry": {
            "panel_width": PANEL_WIDTH,
            "panel_height": PANEL_HEIGHT,
            "overlap": OVERLAP,
        },
        "dates": [],
    }
    if date not in index["dates"]:
        index["dates"].append(date)
    index["updated_at"] = datetime.now(timezone.utc).isoformat()

    blob = _bucket().blob(INDEX_BLOB)
    blob.upload_from_string(json.dumps(index), content_type="application/json")
    logger.info("Updated tapestry manifest: %d panels", len(index["dates"]))
