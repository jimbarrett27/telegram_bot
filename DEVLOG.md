# Devlog

Decisions and milestones for this repo, newest first. One `### entry` per decision or
milestone under a `## YYYY-MM-DD` date header — capture the *why*, not just the *what*.
Maintained via the `/devlog` skill. (Format mirrors `SignalAgents/RESEARCH_LOG.md`.)

## 2026-06-08

### Triage decision + status cleanup (collapse keep-decisions, split auto_rejected)

Three changes after some days of real triage use, driven mainly by wanting clean,
separable labels for a future supervised relevance model. Full spec:
`triage/SPEC-decision-status-cleanup.md`. Built chunk-by-chunk through the
worker/reviewer ensemble.

**Why.** (1) In practice there was no real difference between the `deep` and
`filed` keep-decisions, so the depth choice was just friction producing noisy
labels. (2) The Obsidian stubs gave no signal for which kept papers had actually
been read. (3) "pending" was badly overloaded — 1051 of 1088 "pending" rows were
LLM-screened-out (score 0) papers that never appear in the queue, conflated with
the 37 genuinely awaiting a human decision. Those 1051 are *weak/LLM* negatives;
the 204 `dismissed` are *human* negatives — they must be separate label classes.

**What.** `status` vocabulary is now `pending | kept | dismissed | auto_rejected`
(legacy `deep`/`filed` migrated to `kept`; still rendered if any survive).
- Decision collapsed to `kept` (→ Zotero **and** Obsidian) + `dismissed`.
  `Decision` literal, routing sets, and the Zotero tag (`triage/kept`) updated.
- Obsidian stubs now write to `<inbox>/unread/`; a sibling `read/` folder is
  moved into manually by the user — the app never touches it.
- Screener now inserts non-relevant papers as `auto_rejected` at ingest (not
  `pending`); `get_decided_papers` (History) excludes `pending`+`auto_rejected`.
  `suggested_depth` left untouched — it's a feature, not a label.
- Frontend: single **Keep** button (keys `d`/`f`), depth-hint badge removed.

**Data migration (Alembic rev 004, applied to live DB after backup).** Result
exactly as expected: `kept` 23, `dismissed` 204, `auto_rejected` 1051,
`pending` 37. Downgrade is intentionally lossy (can't recover deep vs filed).

**Zotero backfill (`triage/backfill.py`, one-off).** Pushed the 15 keyless `kept`
papers (12 ex-`filed` that had been Obsidian-only + 3 ex-`deep` whose earlier
push had failed with a transient `'itemType' not provided`). All 23 `kept` papers
now have both a `zotero_key` and an `obsidian_path`; zero failures.

NOTE: requires restarting **both** `telegram_bot` (scanner ingest change) and
`triage-backend` (triage API), plus an Angular rebuild + App Engine redeploy.
The ~23 pre-existing Obsidian stubs keep their old `triage/deep|filed` frontmatter
in the `Papers/` root (cosmetic; the DB — the training data — is clean).
