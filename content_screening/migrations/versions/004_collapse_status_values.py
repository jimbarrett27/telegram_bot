"""Collapse deep/filed to kept; split auto_rejected from pending

Revision ID: 004
Revises: 003
Create Date: 2026-06-08

Data-only migration that normalises the `status` column to the new four-value
vocabulary introduced by the decision-status-cleanup spec:

  pending       — awaiting the user's triage decision (unchanged)
  kept          — user kept it → Zotero + Obsidian  (was deep | filed)
  dismissed     — user rejected it                  (unchanged)
  auto_rejected — LLM screened out (score ≤ 0), never shown in queue
                  (was pending with llm_interest_score IS NULL or ≤ 0)

No schema changes — only UPDATE statements.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Collapse the two legacy "keep" decisions into the unified 'kept' status.
    op.execute("UPDATE articles SET status='kept' WHERE status IN ('deep', 'filed')")

    # Papers the LLM screened out (score 0 or unscored) were never shown in
    # the triage queue but shared the 'pending' label.  Give them their own
    # 'auto_rejected' status so they form a clean weak-negative label class
    # that is excluded from the human-decision History view.
    op.execute(
        "UPDATE articles SET status='auto_rejected' WHERE status='pending'"
        " AND (llm_interest_score IS NULL OR llm_interest_score <= 0)"
    )


def downgrade() -> None:
    # NOTE: this downgrade is intentionally lossy.  'kept' rows cannot be
    # split back into 'deep' vs 'filed' because that distinction was not
    # preserved.  All kept rows are restored as 'deep' (an arbitrary choice).
    # Similarly, 'auto_rejected' rows lose their LLM-score context and are
    # returned to 'pending'.
    op.execute("UPDATE articles SET status='deep' WHERE status='kept'")
    op.execute("UPDATE articles SET status='pending' WHERE status='auto_rejected'")
