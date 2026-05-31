"""Add triage columns to articles

Revision ID: 002
Revises: 001
Create Date: 2026-05-31

Adds the columns the Paper Triage Tool needs onto the existing `articles`
table. The Telegram bot is unaffected: it never reads these columns, and the
screening pipeline now populates `suggested_depth` as a backward-compatible
extra field.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Screening pipeline output: 'file' | 'skim' | 'deep'.
    op.add_column("articles", sa.Column("suggested_depth", sa.Text(), nullable=True))

    # Triage decision lifecycle: 'pending' | 'deep' | 'filed' | 'dismissed'.
    op.add_column(
        "articles",
        sa.Column(
            "status", sa.Text(), nullable=False, server_default="pending"
        ),
    )
    op.add_column("articles", sa.Column("decided_at", sa.Text(), nullable=True))

    # Routing outcomes.
    op.add_column("articles", sa.Column("zotero_key", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("zotero_error", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("obsidian_path", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("obsidian_error", sa.Text(), nullable=True))

    # Retry bookkeeping for the background router.
    op.add_column(
        "articles",
        sa.Column(
            "routing_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column("articles", sa.Column("next_retry_at", sa.Text(), nullable=True))

    op.create_index(
        "idx_articles_status", "articles", ["status", "discovered_at"]
    )
    op.create_index(
        "idx_articles_retry",
        "articles",
        ["next_retry_at"],
        sqlite_where=sa.text("next_retry_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_articles_retry", table_name="articles")
    op.drop_index("idx_articles_status", table_name="articles")
    op.drop_column("articles", "next_retry_at")
    op.drop_column("articles", "routing_attempts")
    op.drop_column("articles", "obsidian_error")
    op.drop_column("articles", "obsidian_path")
    op.drop_column("articles", "zotero_error")
    op.drop_column("articles", "zotero_key")
    op.drop_column("articles", "decided_at")
    op.drop_column("articles", "status")
    op.drop_column("articles", "suggested_depth")
