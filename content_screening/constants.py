"""
Constants for the content screening system.
"""

from pathlib import Path

MODULE_ROOT = Path(__file__).parent

PROMPTS_DIR = MODULE_ROOT / "prompts"

DB_NAME = "content_screening.db"

# Arxiv categories of interest
INTERESTING_ARXIV_CATEGORIES = {
    "cs.AI",
    "cs.CE",
    "cs.CL",
    "cs.LG",
    "stat.AP",
    "stat.CO",
    "stat.ME",
    "stat.ML",
    "stat.TH",
    "math.ST",
    "q-bio.QM",
}

# Pharmacovigilance-related keywords for filtering
PV_KEYWORDS = {
    "drug",
    "pharma",
    "adverse",
    "reaction",
    "medic",
    "duplic",
    "linkage",
}

# How often to scan feeds (in seconds)
SCAN_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours

# Feed entries published within this many days are considered for screening.
# Undated entries are kept regardless; deduplication by external_id (in the
# scanner) prevents anything being screened or stored twice, so this window only
# bounds how far back a *first* sighting can be — it is not a "today only" gate.
SCAN_LOOKBACK_DAYS = 7
