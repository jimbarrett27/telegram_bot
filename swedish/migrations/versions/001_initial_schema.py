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
    op.create_table(
        "flashcards",
        sa.Column("word_to_learn", sa.Text(), nullable=False),
        sa.Column("word_type", sa.Text(), nullable=True),
        sa.Column("n_times_seen", sa.Integer(), nullable=True, default=0),
        sa.Column("difficulty", sa.Float(), nullable=True, default=0.0),
        sa.Column("stability", sa.Float(), nullable=True, default=0.0),
        sa.Column("last_review_epoch", sa.Integer(), nullable=True, default=0),
        sa.Column("next_review_min_epoch", sa.Integer(), nullable=True, default=0),
        sa.PrimaryKeyConstraint("word_to_learn"),
    )


def downgrade() -> None:
    op.drop_table("flashcards")
