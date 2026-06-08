# Spec: triage decision + status cleanup

Status: approved 2026-06-08. Spans two repos — `telegram_bot` (this repo) and
`website` (Angular SPA at `/home/jim/repos/website`).

## Goal

Three behavioural changes plus a data cleanup, so the screening dataset has clean,
separable labels for a future supervised relevance model:

1. Collapse the two "keep" decisions (`deep`, `filed`) into a single **`kept`**
   decision that routes to **both Zotero and Obsidian**.
2. Obsidian stubs go into a `unread/` subfolder; a sibling `read/` folder is
   populated **manually** by the user (the app never writes/reads it).
3. Split the overloaded `pending` status: papers the LLM screened out (score 0,
   never shown in the queue) get their own **`auto_rejected`** status instead of
   masquerading as `pending`.

## New `status` vocabulary

| status          | meaning                                   | label type        |
|-----------------|-------------------------------------------|-------------------|
| `pending`       | awaiting the user's triage decision       | (unlabelled)      |
| `kept`          | user kept it → Zotero + Obsidian          | human positive    |
| `dismissed`     | user rejected it                          | human negative    |
| `auto_rejected` | LLM screened out (score 0), never shown   | weak/LLM negative |

Legacy values `deep`/`filed` are migrated to `kept` (chunk C). The frontend must
still *display* `deep`/`filed` gracefully in History in case any survive.

`suggested_depth` (the screener's `deep|skim|file` hint) is a FEATURE, not a
label — leave it completely untouched everywhere.

---

## Chunk A — decision collapse (triage backend)

Files: `triage/schemas.py`, `triage/routing.py`, `triage/zotero.py`,
`triage/obsidian.py`, `triage/repository.py` (no logic change, rides the type),
`tests/triage/test_obsidian.py`, `tests/triage/test_zotero.py`.

- `schemas.py`: `Decision = Literal["kept", "dismissed"]`. Delete the unused
  `DecideRequest` model. Leave `suggested_depth` on `PaperOut`.
- `routing.py`: `_ZOTERO_DECISIONS = {"kept", "deep"}`,
  `_OBSIDIAN_DECISIONS = {"kept", "deep", "filed"}` (legacy values kept so any
  half-routed old row can still complete). Update the module/comment text that
  says `deep`/`filed`.
- `zotero.py`: rename `_DEEP_TAG = "triage/deep"` → `_KEEP_TAG = "triage/kept"`;
  update comments.
- `obsidian.py`:
  - Add `UNREAD_SUBDIR = "unread"`. `write_stub` writes into
    `vault_root / inbox_subdir / UNREAD_SUBDIR` (so the returned relative path
    includes `.../unread/...`).
  - Frontmatter `status` for a `kept` paper is `"unread"`; the frontmatter `tags`
    become `["paper", "triage/kept"]`. Keep the legacy `_STATUS_BY_DECISION`
    entries (`deep`→`to-read`, `filed`→`filed`) so old code paths/tests are
    explained, but new decisions are `kept`→`unread`.
- Tests: update `test_obsidian.py` (default paper `status="kept"`, expected path
  under `.../unread/...`, frontmatter `status: unread`, tag `triage/kept`;
  replace the `filed`-specific test with an unread-folder assertion). Update
  `test_zotero.py` tag assertion to `triage/kept`.

Idempotency note (no code needed, just don't break it): once routing completes,
`next_retry_at` is cleared and `route_decision` is never called again, so a user
moving a stub file into `read/` later will NOT trigger a rewrite.

## Chunk B — `auto_rejected` at ingest + history exclusion

Files: `content_screening/database.py`, `content_screening/orm_models.py`
(`article_dataclass_to_orm`), `content_screening/scanner.py`,
`triage/repository.py`, `content_screening/orm_models.py` status comment, tests.

- `article_dataclass_to_orm(article, discovered_at, status="pending")` — add an
  optional `status` param, pass it through to `ArticleORM(status=...)`.
- `insert_article(article, status="pending")` — thread the param through to the
  conversion.
- `scanner.process_new_articles`: compute
  `status = "pending" if is_relevant else "auto_rejected"` and pass it to
  `insert_article`. (Relevant papers still land as `pending` for the queue.)
- `triage/repository.py`: `get_decided_papers` must exclude `auto_rejected`:
  `where(ArticleORM.status.notin_(["pending", "auto_rejected"]))` so History
  stays human-decisions-only.
- Update the `status` lifecycle comment in `orm_models.py` to list the four
  values.
- Tests: a scanner/ingest test that a non-relevant article is inserted with
  `status="auto_rejected"` and a relevant one with `status="pending"`; a
  `get_decided_papers` test confirming `auto_rejected` rows are excluded.

## Chunk C — Alembic rev 004 (data migration, DB-only)

New revision after `003`. Up:
```sql
UPDATE articles SET status='kept'         WHERE status IN ('deep','filed');
UPDATE articles SET status='auto_rejected' WHERE status='pending'
    AND (llm_interest_score IS NULL OR llm_interest_score <= 0);
```
Down (lossy — document it): `UPDATE articles SET status='deep' WHERE status='kept'`
and `UPDATE articles SET status='pending' WHERE status='auto_rejected'`.

Generate with `--autogenerate`? NO — this is data-only, write the revision by
hand using `op.execute(...)`. Do NOT run `upgrade` here; applying to the live DB
is an orchestrator deploy step (after a backup).

Run alembic from repo root with `PYTHONPATH=.` and
`-c content_screening/alembic.ini` (url is relative). Verify the file is created
and `alembic history` shows it on top of 003. Use `alembic upgrade head --sql`
to sanity-check the SQL without touching data.

## Chunk D — frontend (website repo)

Files under `/home/jim/repos/website/src/app/triage/`:
`models/paper.model.ts`, `components/paper-card/paper-card.component.ts`,
`shortcuts.ts`, `pages/queue/queue.component.ts`.

- `paper.model.ts`:
  `TriageStatus = 'pending' | 'kept' | 'dismissed' | 'auto_rejected' | 'deep' | 'filed'`
  (legacy + auto_rejected included for completeness). `Decision = 'kept' | 'dismissed'`.
- `paper-card`: remove the depth-badge markup, its CSS (`.badge*`), and
  `depthHint()`. Replace the **Deep** + **File** buttons with one **Keep** button
  emitting `'kept'`. Update `statusLabel` (add `kept`→'Kept', `auto_rejected`,
  keep `deep`/`filed`). Update `routingBadges`: Zotero applies when
  `status==='kept' || status==='deep'`; Obsidian when
  `status==='kept' || status==='deep' || status==='filed'`. Add a `.decided-kept`
  style.
- `shortcuts.ts`: replace the `d`/`f` entries with one entry — keys `['d','f']`,
  description `Keep (Zotero + Obsidian)`.
- `queue.component.ts`: `handleKey` — both `'d'` and `'f'` call `decide('kept')`;
  `decisionLabel` maps `kept`→'Kept'.
- `npm run build` and `npm run lint` must pass.

## Chunk E — one-off Zotero backfill

New file `triage/backfill.py`, runnable as `uv run python -m triage.backfill`.

- Open a session; select `kept` papers that are NOT routing-complete (no
  `zotero_key`). For each: reset `routing_attempts=0`, `zotero_error=None`,
  `next_retry_at=None`, then call `routing.route_and_schedule(paper, settings)`
  (idempotent — pushes Zotero, skips the existing Obsidian stub). Commit.
- Print a summary: number pushed, number failed (+ each error).
- Must be a no-op-safe script (re-runnable). Needs Zotero + Obsidian enabled in
  the environment at run time — this is an orchestrator/deploy step, not run in
  tests. Add a light unit test with Zotero mocked if feasible, else none.

---

## Deploy order (orchestrator, after all chunks merged + green)

1. Back up the live DB: `cp content_screening.db content_screening.db.bak-<ts>`.
2. `PYTHONPATH=. uv run alembic -c content_screening/alembic.ini upgrade head`.
3. `uv run python -m triage.backfill` (CONFIRM with user first — live Zotero writes).
4. User: `sudo systemctl restart telegram_bot triage-backend` (both services —
   scanner + triage code changed; see the two-services note).
5. User: rebuild + redeploy the Angular SPA to App Engine.

## Expected data after migration (sanity check)

From the live DB on 2026-06-08 (rev 003): `pending` 1088, `dismissed` 204,
`filed` 12, `deep` 11. After rev 004: `kept` 23, `dismissed` 204,
`auto_rejected` ~1051, `pending` ~37. Backfill pushes 15 papers to Zotero
(12 ex-filed + 3 ex-deep whose push previously failed with `'itemType' not
provided` — if those 3 fail again, fix the Zotero template bug).
