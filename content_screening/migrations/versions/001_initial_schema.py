"""Initial schema baseline

Revision ID: 001
Revises:
Create Date: 2025-01-18

This migration creates the baseline schema matching the existing database.
For existing databases, mark this migration as complete without running it:
    alembic stamp 001
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # articles table
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("authors", sa.Text(), nullable=True),
        sa.Column("categories", sa.Text(), nullable=True),
        sa.Column("keywords_matched", sa.Text(), nullable=True),
        sa.Column("discovered_at", sa.Integer(), nullable=False),
        sa.Column("llm_interest_score", sa.Float(), nullable=True),
        sa.Column("llm_reasoning", sa.Text(), nullable=True),
        sa.Column("llm_tags", sa.Text(), nullable=True),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("metadata", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "external_id", name="uq_source_external"),
    )
    op.create_index("idx_articles_source_type", "articles", ["source_type"])
    op.create_index("idx_articles_discovered_at", "articles", ["discovered_at"])

    # article_ratings table
    op.create_table(
        "article_ratings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("rated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # pending_article_notifications table
    op.create_table(
        "pending_article_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("notified_at", sa.Integer(), nullable=False),
        sa.Column("rating_received", sa.Integer(), nullable=True, default=0),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id"),
    )

    # scan_history table
    op.create_table(
        "scan_history",
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("last_scan_epoch", sa.Integer(), nullable=False),
        sa.Column("articles_found", sa.Integer(), nullable=True, default=0),
        sa.Column("articles_interesting", sa.Integer(), nullable=True, default=0),
        sa.PrimaryKeyConstraint("source_type"),
    )


def downgrade() -> None:
    op.drop_table("scan_history")
    op.drop_table("pending_article_notifications")
    op.drop_table("article_ratings")
    op.drop_index("idx_articles_discovered_at", table_name="articles")
    op.drop_index("idx_articles_source_type", table_name="articles")
    op.drop_table("articles")
