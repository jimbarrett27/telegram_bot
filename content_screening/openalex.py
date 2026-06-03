"""OpenAlex discovery source.

A third, additive discovery source alongside the arXiv and journal RSS feeds.
OpenAlex (https://api.openalex.org, free, no key) gives structured metadata:
topic classification, per-author affiliations + positions, the citation graph,
and near-universal DOIs.

A paper becomes a candidate if ANY configured signal matches; each matching
signal is recorded on ``Article.surfaced_by``:

- ``topic``       -- the work has one of the configured topics (any position)
- ``author``      -- authored by a monitored author (OpenAlex ID or ORCID)
- ``citation``    -- cites one of the configured seed papers
- ``institution`` -- cites a first/last-author work of a watched institution

All candidates flow through the normal screen -> embed -> insert pipeline; the
broad keyword net (shared with the other sources) still annotates
``keywords_matched``. Networking is funnelled through ``_get`` so tests can mock
a single seam.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import requests
import yaml

from content_screening.constants import (
    MODULE_ROOT,
    PV_KEYWORDS,
    SCAN_LOOKBACK_DAYS,
    find_matching_keywords,
)
from content_screening.database import normalize_doi
from content_screening.models import Article, SourceType
from util.logging_util import setup_logger

logger = setup_logger(__name__)

OPENALEX_BASE = "https://api.openalex.org"
DEFAULT_MAILTO = "jimbarrett27@gmail.com"
DISCOVERY_CONFIG_PATH = MODULE_ROOT / "data" / "discovery.yaml"

# Only the fields we actually map -- keeps payloads small.
WORK_SELECT = (
    "id,doi,ids,title,authorships,publication_date,"
    "abstract_inverted_index,primary_location,topics"
)
PER_PAGE = 200
CITES_BATCH = 50  # OpenAlex allows ~50 OR'd ids in a single filter
# Safety bound so a misconfigured/huge filter can't paginate forever.
MAX_PAGES = 25


# --- Config -----------------------------------------------------------------


@dataclass
class DiscoveryConfig:
    """Parsed ``discovery.yaml``."""

    mailto: str = DEFAULT_MAILTO
    topics: List[dict] = field(default_factory=list)          # [{id, name}]
    monitored_authors: List[str] = field(default_factory=list)
    seed_papers: List[str] = field(default_factory=list)
    institutions: List[dict] = field(default_factory=list)    # [{id, name, author_positions}]


def load_discovery_config(config_path: Path = DISCOVERY_CONFIG_PATH) -> DiscoveryConfig:
    """Load discovery configuration from YAML (empty/missing -> empty config)."""
    if not config_path.exists():
        logger.warning(f"Discovery config not found at {config_path}")
        return DiscoveryConfig()

    with open(config_path, "r") as f:
        data = yaml.safe_load(f) or {}

    return DiscoveryConfig(
        mailto=data.get("mailto") or DEFAULT_MAILTO,
        topics=data.get("topics") or [],
        monitored_authors=data.get("monitored_authors") or [],
        seed_papers=data.get("seed_papers") or [],
        institutions=data.get("institutions") or [],
    )


# --- HTTP / pagination ------------------------------------------------------


def _get(path: str, params: dict, mailto: str) -> dict:
    """GET an OpenAlex endpoint with the polite-pool ``mailto`` attached."""
    query = dict(params)
    query["mailto"] = mailto
    response = requests.get(f"{OPENALEX_BASE}/{path}", params=query, timeout=30)
    response.raise_for_status()
    return response.json()


def _paginate_works(
    filter_str: str, mailto: str, select: str = WORK_SELECT
) -> Iterator[dict]:
    """Yield works matching ``filter_str``, following the cursor."""
    cursor = "*"
    pages = 0
    while cursor and pages < MAX_PAGES:
        data = _get(
            "works",
            {
                "filter": filter_str,
                "per_page": PER_PAGE,
                "cursor": cursor,
                "select": select,
                "sort": "publication_date:desc",
            },
            mailto,
        )
        for work in data.get("results", []):
            yield work
        cursor = (data.get("meta") or {}).get("next_cursor")
        pages += 1


def _from_date(lookback_days: int = SCAN_LOOKBACK_DAYS) -> str:
    """ISO date ``lookback_days`` ago, for ``from_publication_date`` filters."""
    return (date.today() - timedelta(days=lookback_days)).isoformat()


def _batched(items: List[str], size: int) -> Iterator[List[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


# --- Mapping ----------------------------------------------------------------


def reconstruct_abstract(inverted_index: Optional[dict]) -> Optional[str]:
    """Rebuild plain-text abstract from OpenAlex's ``abstract_inverted_index``."""
    if not inverted_index:
        return None
    positions: Dict[int, str] = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions[i] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


def _short_id(entity_id: Optional[str]) -> Optional[str]:
    """``https://openalex.org/W123`` -> ``W123``."""
    if not entity_id:
        return None
    return entity_id.rstrip("/").split("/")[-1]


def _is_future_date(publication_date: Optional[str]) -> bool:
    """OpenAlex occasionally carries bogus future publication dates -- guard."""
    if not publication_date:
        return False
    try:
        pub = datetime.strptime(publication_date, "%Y-%m-%d").date()
    except ValueError:
        return False
    return pub > date.today()


def _map_authorships(authorships: List[dict]) -> tuple[List[str], List[dict]]:
    """Return (author display names, rich authorship records for metadata)."""
    names: List[str] = []
    rich: List[dict] = []
    for a in authorships or []:
        author = a.get("author") or {}
        name = author.get("display_name") or ""
        if name:
            names.append(name)
        rich.append(
            {
                "name": name,
                "position": a.get("author_position"),
                "author_id": _short_id(author.get("id")),
                "orcid": author.get("orcid"),
                "institutions": [
                    inst.get("display_name")
                    for inst in (a.get("institutions") or [])
                    if inst.get("display_name")
                ],
            }
        )
    return names, rich


def _work_to_article(work: dict, surfaced_by: List[str]) -> Optional[Article]:
    """Map an OpenAlex work to an ``Article``; ``None`` if unusable/bogus."""
    title = (work.get("title") or "").strip()
    if not title:
        return None

    publication_date = work.get("publication_date")
    if _is_future_date(publication_date):
        logger.debug("Skipping work with future publication date: %s", publication_date)
        return None

    work_id = _short_id(work.get("id"))
    if not work_id:
        return None

    doi = normalize_doi(work.get("doi"))
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    names, rich_authors = _map_authorships(work.get("authorships", []))

    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    venue = source.get("display_name")
    url = primary.get("landing_page_url") or (
        f"https://doi.org/{doi}" if doi else f"https://openalex.org/{work_id}"
    )

    topics = work.get("topics") or []
    topic_names = [t.get("display_name") for t in topics if t.get("display_name")]
    topic_ids = [_short_id(t.get("id")) for t in topics if t.get("id")]

    keywords_matched = find_matching_keywords(f"{title} {abstract or ''}", PV_KEYWORDS)

    return Article(
        external_id=work_id,
        source_type=SourceType.OPENALEX,
        title=title,
        abstract=abstract,
        doi=doi,
        url=url,
        authors=names,
        categories=topic_names,
        keywords_matched=keywords_matched,
        surfaced_by=list(surfaced_by),
        metadata={
            "openalex_id": work_id,
            "venue": venue,
            "publication_date": publication_date,
            "topic_ids": topic_ids,
            "authorships": rich_authors,
        },
    )


# --- Signals ----------------------------------------------------------------


def _topic_works(cfg: DiscoveryConfig, from_date: str) -> Iterator[tuple[dict, str]]:
    """Recent works with any of the configured topics (signal: ``topic``)."""
    topic_ids = [t["id"] for t in cfg.topics if t.get("id")]
    if not topic_ids:
        return
    filter_str = f"topics.id:{'|'.join(topic_ids)},from_publication_date:{from_date}"
    for work in _paginate_works(filter_str, cfg.mailto):
        yield work, "topic"


def _author_works(cfg: DiscoveryConfig, from_date: str) -> Iterator[tuple[dict, str]]:
    """Recent works by monitored authors (signal: ``author``).

    Splits the watchlist into OpenAlex author IDs (start with 'A') and ORCIDs.
    """
    ids = [a for a in cfg.monitored_authors if str(a).upper().startswith("A")]
    orcids = [a for a in cfg.monitored_authors if not str(a).upper().startswith("A")]

    for author_ids in _batched(ids, CITES_BATCH):
        filter_str = (
            f"authorships.author.id:{'|'.join(author_ids)},"
            f"from_publication_date:{from_date}"
        )
        for work in _paginate_works(filter_str, cfg.mailto):
            yield work, "author"

    for orcid_batch in _batched(orcids, CITES_BATCH):
        filter_str = (
            f"authorships.author.orcid:{'|'.join(orcid_batch)},"
            f"from_publication_date:{from_date}"
        )
        for work in _paginate_works(filter_str, cfg.mailto):
            yield work, "author"


def _citers_of(seed_ids: List[str], cfg: DiscoveryConfig, from_date: str, signal: str) -> Iterator[tuple[dict, str]]:
    """Recent works citing any of ``seed_ids`` (batched into ``cites:`` filters)."""
    for batch in _batched(seed_ids, CITES_BATCH):
        filter_str = f"cites:{'|'.join(batch)},from_publication_date:{from_date}"
        for work in _paginate_works(filter_str, cfg.mailto):
            yield work, signal


def _seed_citers(cfg: DiscoveryConfig, from_date: str) -> Iterator[tuple[dict, str]]:
    """Citers of explicitly configured seed papers (signal: ``citation``)."""
    if not cfg.seed_papers:
        return
    yield from _citers_of(list(cfg.seed_papers), cfg, from_date, "citation")


def _resolve_institution_seed_works(institution: dict, mailto: str) -> List[str]:
    """Work IDs where the institution appears at a configured author position.

    OpenAlex matches an institution at ANY author position, so we post-filter
    client-side on ``author_position`` (e.g. first/last) for precision.
    """
    inst_id = institution.get("id")
    if not inst_id:
        return []
    positions = set(institution.get("author_positions") or ["first", "last"])

    seed_ids: List[str] = []
    filter_str = f"authorships.institutions.id:{inst_id}"
    for work in _paginate_works(
        filter_str, mailto, select="id,authorships"
    ):
        for a in work.get("authorships", []):
            if a.get("author_position") not in positions:
                continue
            if any(_short_id(i.get("id")) == inst_id for i in (a.get("institutions") or [])):
                wid = _short_id(work.get("id"))
                if wid:
                    seed_ids.append(wid)
                break
    return seed_ids


def _institution_citers(cfg: DiscoveryConfig, from_date: str) -> Iterator[tuple[dict, str]]:
    """Citers of watched institutions' first/last-author works (signal: ``institution``)."""
    for institution in cfg.institutions:
        seed_ids = _resolve_institution_seed_works(institution, cfg.mailto)
        logger.info(
            "Institution %s: %d seed works (positions=%s)",
            institution.get("name") or institution.get("id"),
            len(seed_ids),
            institution.get("author_positions"),
        )
        yield from _citers_of(seed_ids, cfg, from_date, "institution")


def _topic_gated_out(
    article: Article, configured_topic_ids: set, focused_topic_ids: set
) -> bool:
    """Whether a topic-surfaced work should be dropped by the keyword gate.

    Dropped iff it matched *only* gated (broad) topics — none of the focused,
    ungated topics — and carries no PV keyword. Works that match a focused topic
    are always kept; works with a keyword are always kept.
    """
    matched = set(article.metadata.get("topic_ids") or []) & configured_topic_ids
    if matched & focused_topic_ids:
        return False  # matched a focused topic -> ungated
    return not article.keywords_matched


# --- Public entry point -----------------------------------------------------


def fetch_openalex_articles(
    config: Optional[DiscoveryConfig] = None,
    lookback_days: int = SCAN_LOOKBACK_DAYS,
) -> List[Article]:
    """Fetch candidate articles from all configured OpenAlex signals.

    Works surfaced by multiple signals are merged into a single ``Article`` with
    the union of ``surfaced_by`` tags (deduped by OpenAlex work id within the
    fetch). Cross-source dedup against existing DB rows happens later in the
    scanner.
    """
    if config is None:
        config = load_discovery_config()

    from_date = _from_date(lookback_days)

    # Topic keyword gate: works surfaced *only* by a broad (require_keyword) topic
    # must also match a PV keyword; works matching a focused topic are ungated.
    # Author/citation/institution signals are never gated.
    configured_topic_ids = {t["id"] for t in config.topics if t.get("id")}
    gated_topic_ids = {
        t["id"] for t in config.topics if t.get("id") and t.get("require_keyword")
    }
    focused_topic_ids = configured_topic_ids - gated_topic_ids
    signal_streams = (
        _topic_works(config, from_date),
        _author_works(config, from_date),
        _seed_citers(config, from_date),
        _institution_citers(config, from_date),
    )

    by_id: Dict[str, Article] = {}
    for stream in signal_streams:
        try:
            for work, signal in stream:
                work_id = _short_id(work.get("id"))
                if not work_id:
                    continue
                existing = by_id.get(work_id)
                if existing is not None:
                    if signal not in existing.surfaced_by:
                        existing.surfaced_by.append(signal)
                    continue
                article = _work_to_article(work, [signal])
                if article is None:
                    continue
                if signal == "topic" and _topic_gated_out(
                    article, configured_topic_ids, focused_topic_ids
                ):
                    continue
                by_id[work_id] = article
        except requests.RequestException as exc:
            logger.error("OpenAlex fetch failed for a signal stream: %s", exc)

    articles = list(by_id.values())
    logger.info("Fetched %d unique works from OpenAlex", len(articles))
    return articles
