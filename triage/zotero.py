"""Pushes triaged ``kept`` papers into the personal Zotero library (build step 7).

A ``kept`` decision (and legacy ``deep``) pushes to Zotero. The client and API
key are resolved lazily so neither ``pyzotero`` nor GCP creds are needed for
local/dev runs that leave Zotero unconfigured. Idempotency (skip if a
``zotero_key`` already exists) is the caller's responsibility — see
``routing.py`` — so the step-8 retry loop is safe to run repeatedly.
"""

from functools import lru_cache

from content_screening.orm_models import ArticleORM
from util.logging_util import setup_logger

logger = setup_logger(__name__)

# Tag stamped on every pushed item, mirroring the Obsidian `triage/kept` tag.
_KEEP_TAG = "triage/kept"


def _item_type(source_type: str) -> str:
    """arXiv papers are preprints; everything else is treated as a journal article."""
    return "preprint" if source_type == "arxiv" else "journalArticle"


def _creators(authors: list[str] | None) -> list[dict]:
    """Map author name strings to Zotero creator dicts (best-effort name split)."""
    creators: list[dict] = []
    for raw in authors or []:
        name = raw.strip()
        if not name:
            continue
        if " " in name:
            first, last = name.rsplit(" ", 1)
            creators.append(
                {"creatorType": "author", "firstName": first, "lastName": last}
            )
        else:
            # Single token (e.g. an organisation): use Zotero's single-field name.
            creators.append({"creatorType": "author", "name": name})
    return creators


@lru_cache(maxsize=1)
def _client():
    """Build (and cache) the pyzotero client for the personal library.

    Both the user ID and the API key come from GCP Secret Manager
    (ZOTERO_USER_ID / ZOTERO_API_KEY). Imports are deferred so the dependency
    and GCP creds are only required when Zotero is actually configured.
    """
    from pyzotero import zotero

    from gcp_util.secrets import get_zotero_api_key, get_zotero_user_id

    return zotero.Zotero(get_zotero_user_id(), "user", get_zotero_api_key())


def push_paper(paper: ArticleORM) -> str:
    """Create a Zotero item for ``paper`` and return its item key.

    Raises on any failure; the caller records the error on the row rather than
    letting the decision fail.
    """
    zot = _client()

    item_type = _item_type(paper.source_type)
    template = zot.item_template(item_type)
    template["title"] = paper.title
    template["abstractNote"] = paper.abstract or ""
    template["url"] = paper.url or ""
    template["tags"] = [{"tag": _KEEP_TAG}]

    creators = _creators(paper.authors)
    if creators:
        template["creators"] = creators

    # arXiv id goes in the preprint `archiveID` field where the template has one.
    if paper.source_type == "arxiv" and paper.external_id and "archiveID" in template:
        template["archiveID"] = paper.external_id

    resp = zot.create_items([template])
    if resp.get("failed"):
        raise RuntimeError(f"Zotero rejected the item: {resp['failed']}")
    try:
        return resp["successful"]["0"]["key"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"unexpected Zotero create response: {resp}") from exc
