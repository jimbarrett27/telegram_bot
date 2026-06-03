"""Add OpenAlex source columns to articles

Revision ID: 003
Revises: 002
Create Date: 2026-06-03

Adds the columns the OpenAlex discovery source needs onto the existing
`articles` table:
- `doi`: normalized DOI, the primary cross-source dedup key (indexed).
- `surfaced_by`: JSON list of the discovery signal(s) that surfaced the paper
  ('keyword' | 'topic' | 'author' | 'citation' | 'institution').

Both are nullable and backward-compatible: the Telegram bot and existing
arXiv/RSS path are unaffected.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("doi", sa.Text(), nullable=True))
    op.add_column("articles", sa.Column("surfaced_by", sa.Text(), nullable=True))
    op.create_index("idx_articles_doi", "articles", ["doi"])


def downgrade() -> None:
    op.drop_index("idx_articles_doi", table_name="articles")
    op.drop_column("articles", "surfaced_by")
    op.drop_column("articles", "doi")
