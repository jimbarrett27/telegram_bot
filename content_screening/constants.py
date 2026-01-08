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
