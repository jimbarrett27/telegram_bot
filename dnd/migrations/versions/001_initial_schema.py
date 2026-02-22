"""Initial schema for D&D game system

Revision ID: 001
Revises:
Create Date: 2026-02-22
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
        "games",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="recruiting"),
        sa.Column("adventure_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("current_player_id", sa.Integer(), nullable=True),
        sa.Column("turn_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id"),
    )

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("telegram_user_id", sa.Integer(), nullable=False),
        sa.Column("telegram_username", sa.Text(), nullable=False),
        sa.Column("character_name", sa.Text(), nullable=False),
        sa.Column("character_class", sa.Text(), nullable=False),
        sa.Column("hp", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_hp", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("joined_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "telegram_user_id", name="uq_game_player"),
    )
    op.create_index("idx_players_game_id", "players", ["game_id"])

    op.create_table(
        "game_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("turn_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_player_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_game_events_game_id", "game_events", ["game_id"])


def downgrade() -> None:
    op.drop_table("game_events")
    op.drop_table("players")
    op.drop_table("games")
