"""
Utilities for working with preprints from arxiv and the arxiv site and feeds
"""

from util.constants import INTERESTING_ARXIV_CATEGORIES, PV_KEYWORDS

import feedparser  # type: ignore
from html2text import html2text


def get_arxiv_rss_url(arxiv_category: str):
    """
    Gets the rss url for the given arxiv category
    """
    return f"http://rss.arxiv.org/rss/{arxiv_category}"


def get_latest_ids_and_abstracts():
    """
    Fetches all the latest paper ids and their abstracts

    TODO: refactor the arxiv specific stuff into arxiv.py
    """
    paper_id_to_abstract = {}
    for category in INTERESTING_ARXIV_CATEGORIES:
        url = get_arxiv_rss_url(category)
        rss_content = feedparser.parse(url)
        for entry in rss_content["entries"]:
            abstract = html2text(entry["summary"])
            if not any(k in abstract for k in PV_KEYWORDS):
                continue
            paper_id = entry["id"].split("/")[-1]
            paper_id_to_abstract[paper_id] = abstract

    return paper_id_to_abstract

def make_link_to_arxiv(paper_id):
    return f"https://arxiv.org/abs/{paper_id}"


