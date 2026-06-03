# OpenAlex as an additional discovery source — design & plan

Status: **built 2026-06-03** (`openalex.py`, migration 003, cross-source dedup,
`discovery.yaml`, scanner wiring, frontend `surfaced_by` chips; topic set finalized
to T11943/T10508/T13702/T11396, EHR dropped). Picks up from the
paper-triage work. Downstream of ingestion (LLM screening, embeddings, triage UI,
Zotero/Obsidian routing) is already live and unchanged by this.

## Goal

Add **OpenAlex** as a third discovery source alongside the existing **arXiv RSS**
and **journal RSS** feeds (both kept). OpenAlex gives structured metadata,
topic-based filtering (precision), per-author affiliations, citations, and DOIs —
unifying the "richer screening signals" we want into one queryable API.

## Decisions made (with the user)

- **Keep arXiv RSS** (same-day freshness) and **keep journal RSS** (a decent chunk
  still carry full info, e.g. Springer/Lancet). OpenAlex is **additive**, not a
  replacement.
- **Slight delay is acceptable** (OpenAlex indexes post-publication, days–weeks).
- Must **deduplicate across all three sources** (same paper can appear in more than
  one). See dedup design below.
- This **subsumes** the previously-scoped author-watchlist + citation + UMC-institution
  monitoring — they're all just OpenAlex filters now (see also the memory note
  "Screening-refinement design").

## Why OpenAlex (verified live via the API, 2026-06-03)

Base URL `https://api.openalex.org`; free, no key; pass `mailto=jimbarrett27@gmail.com`
for the polite pool. All numbers below were probed live.

- **Topics give precision** (fixes "keyword screening too broad"): topic
  **`T11943` "Pharmacovigilance and Adverse Drug Reactions"** (34,083 works);
  concept `C57658597` "Pharmacovigilance" (35,195). Filtering by topic replaces the
  blunt keyword stems (`drug`/`medic`/… which match ~everything).
  - Recent volume: `topics.id:T11943` + `from_publication_date` last 30d ≈ **587
    works (~20/day)** — focused and manageable.
- **Abstracts ~72%** present (`abstract_inverted_index`) on a topic sample — better
  than the patchy per-feed situation, but **NOT 100%**: Elsevier/ScienceDirect
  restrict open abstracts (only ~25% of ScienceDirect-specific had them). Some papers
  stay title-only regardless of source.
- **DOI ~98%** present (49/50 topic works) → strong cross-source dedup key.
  - NOTE: OpenAlex does **not** reliably expose arXiv IDs in `ids` (0/50 topic works;
    the "Attention is all you need" work had only openalex/doi/mag) → arXiv↔OpenAlex
    matching must lean on **normalized title**.
- **Per-author affiliations + position**: each `authorships[]` entry has its own
  `institutions[]` AND `author_position` (`first`/`middle`/`last`). Fixes the
  "Unknown authors" problem entirely.
- **Citations**: `filter=cites:<workid>` returns citers; batch ~50 IDs with `|`,
  add `from_publication_date` for recency.
- **Institution = first-class**: Uppsala Monitoring Centre (UMC) =
  **`I111684115`** (ROR `057rhqk62`, 568 works). `filter=authorships.institutions.id:I111684115`
  matches ANY author position → post-filter on `author_position` client-side for
  first/last. Of UMC's 537 affiliated works: **314 first-author, 199 last-author,
  380 first-or-last** (157 are minor-collaborator). User leans toward the
  **first/last subset (380)** as the citation seed for precision. ~318 papers cited
  UMC's top-50 works in ~4 months (~80–150/mo full corpus); note the most-cited UMC
  works are broad review/definition papers cited by all of PV — curating to specific
  **method** papers (BCPNN / disproportionality / vigiRank) is higher precision.
- **Author monitoring**: arXiv API `search_query=au:Lastname_F` works
  (`au:bengio`→739, `au:Hinton_G`→1). Caveat: name disambiguation (common surnames
  match multiple people). Simpler ongoing route for arXiv = match watchlist names
  against authors already extracted from the daily feed; OpenAlex `authorships.author.id`
  (resolved author IDs) is the robust cross-source route.

## Architecture: OR'd inclusion signals

A paper becomes a candidate iff ANY signal fires, and we record **which** via a
`surfaced_by` tag (also a useful ML feature / positive-label hint):

```
candidate iff: keyword_match            (existing, broad recall)
            OR topic_match              (OpenAlex topics — precise)
            OR monitored_author
            OR cites_seed_paper
            OR cites_institution (UMC)
```

High-precision signals (author / citation / institution) can bypass the keyword
filter, and optionally skip the LLM relevance gate (you want everything they
publish). Keyword stays as the broad net; the LLM and the eventual embedding
classifier refine. All candidates → embed → screen → queue, as today.

## Cross-source dedup design

Current dedup is per-source: `article_exists(source_type, external_id)` with a unique
constraint `(source_type, external_id)` — the SAME paper from different sources gets
different keys → would duplicate. Fix = a **cross-source identity key** checked before
insert:

1. **DOI (primary)** — normalize (lowercase, strip `https://doi.org/`). OpenAlex
   ~always has it; many journal RSS links ARE DOIs (Wiley etc.); arXiv canonical DOI
   = `10.48550/arXiv.<id>`.
2. **Normalized title (fallback)** — lowercase, strip punctuation/whitespace, decode
   HTML entities (saw `<em>` in titles). Only reliable bridge for arXiv↔OpenAlex.

Mechanics: at scan start, load existing rows' DOIs + normalized titles into an
in-memory set (a few thousand rows — trivial), skip any incoming candidate that
matches; also dedups within a run across sources.

**Recommended (small) schema change**: add a nullable, indexed **`doi`** column to
`articles` (Alembic migration). Populate from OpenAlex always; derive for arXiv
(`10.48550/arXiv.<id>`) and RSS (DOI-in-link where present). DOI-primary dedup is far
more robust than title-only, and DOI is independently useful (OpenAlex abstract-by-DOI,
citation linking, cleaner Zotero items). Title-only dedup works without the migration
if we want to defer it.

## Abstract enrichment (optional, best-effort)

For papers ingested with an empty abstract (ScienceDirect etc.), look up OpenAlex by
DOI/title and reconstruct from `abstract_inverted_index`:

```python
def reconstruct_abstract(inv):
    if not inv: return None
    pos = {}
    for word, idxs in inv.items():
        for i in idxs: pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))
```

Coverage is partial (~70% topic-wide, ~25% ScienceDirect-only). Make it re-runnable
so lagged papers get upgraded later, and **re-embed only after** an abstract is
recovered (the user explicitly wants to avoid embedding title-only then re-embedding).

## Open decisions (need user input next session)

1. **Topics** for the OpenAlex net: `T11943` (pharmacovigilance) as core — add others?
   (signal detection, ML-in-medicine, causal inference, record linkage…). Could also
   use concepts. Needs the user's picks.
2. **Citation seed scope**: whole UMC institution vs. the first/last-author subset
   (380) vs. a hand-picked list of UMC method papers (highest precision).
3. **Author watchlist** contents (names / OpenAlex author IDs).
4. Whether high-precision signals **skip the LLM screen** (auto-queue) or still get
   screened.

## Data-hygiene caveats

- OpenAlex has some **bogus future publication dates** (saw `2028-01-28`) and
  **duplicate records** — filter/guard on ingest.
- Respect `from_publication_date` windows + dedup to bound volume.

## Implementation plan / phasing

1. **`content_screening/openalex.py`** — query builder (works by `topics.id` +
   `from_publication_date`, `cites:` batches, `authorships.institutions.id`, author),
   pagination (cursor), `abstract_inverted_index` reconstruction, map OpenAlex work →
   `Article` (title, authors+affiliations, DOI, url, date, venue), `mailto` param.
2. **`doi` column** — Alembic migration + populate logic; backfill existing rows where
   derivable.
3. **Cross-source dedup helper** — DOI + normalized-title; used by all sources.
4. **`discovery.yaml`** config — topics, monitored authors, seed papers, watched
   institutions (mirrors `feeds.yaml`).
5. **Rewire the scanner** — run all three sources, merge candidates, dedup, then the
   existing screen+embed+insert path. Add `surfaced_by`. Daily summary already exists.
6. **Tests** — dedup logic, OpenAlex→Article mapping, abstract reconstruction
   (mock the API; no network in tests).

## Relevant existing code (touchpoints)

- `content_screening/scanner.py` — `process_new_articles` (screen+embed+insert),
  `run_arxiv_scan`/`run_rss_scan`/`run_full_scan`, `format_scan_summary`,
  `count_pending_triage`. Add an OpenAlex source + dedup here.
- `content_screening/arxiv_feed.py`, `rss_feed.py` — existing source fetchers
  (`fetch_*`), `_is_recent` look-back, author/abstract parsing.
- `content_screening/models.py` — `Article` dataclass (has `embedding`, `metadata`,
  no `doi` yet); `orm_models.py` — `ArticleORM` + `article_dataclass_to_orm`
  (add `doi`); `database.py` — `article_exists`/`insert_article` (cross-source dedup).
- `content_screening/embeddings.py` — `get_embedding` (OpenRouter `gemini-embedding-2`,
  3072-d, float32 via `array`); embedding-on-ingest already wired.
- `content_screening/constants.py` — `SCAN_LOOKBACK_DAYS`, keywords, arxiv categories.

## Verified OpenAlex query reference (copy-paste)

```python
import requests
B = "https://api.openalex.org"; MAILTO = {"mailto": "jimbarrett27@gmail.com"}

# topic works in a date window (the core discovery query)
requests.get(f"{B}/works", params={
    "filter": "topics.id:T11943,from_publication_date:2026-05-03",
    "sort": "publication_date:desc", "per_page": 200, "cursor": "*",
    "select": "id,doi,ids,title,authorships,publication_date,abstract_inverted_index,primary_location",
    **MAILTO})

# citers of seed works (batch ~50 ids with |), recent only
requests.get(f"{B}/works", params={"filter": "cites:W123|W456,from_publication_date:2026-05-01", **MAILTO})

# institution resolve + its works (post-filter author_position for first/last)
requests.get(f"{B}/institutions", params={"search": "Uppsala Monitoring Centre", **MAILTO})  # -> I111684115
requests.get(f"{B}/works", params={"filter": "authorships.institutions.id:I111684115", "per_page": 200, "cursor": "*", **MAILTO})
```
</content>
