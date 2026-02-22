"""Add character attributes, inventory, and spell slots

Revision ID: 002
Revises: 001
Create Date: 2026-02-22
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
    # Add ability score columns to players
    for attr in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
        op.add_column("players", sa.Column(attr, sa.Integer(), nullable=False, server_default="10"))

    # Create inventory_items table
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("item_name", sa.Text(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False, server_default="gear"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("equipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("properties", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_inventory_player_id", "inventory_items", ["player_id"])
    op.create_index("idx_inventory_game_id", "inventory_items", ["game_id"])

    # Create spell_slots table
    op.create_table(
        "spell_slots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=False),
        sa.Column("level_1", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_2", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_3", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_4", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_5", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_6", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_7", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_8", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level_9", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_level_1", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_level_2", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_level_3", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_level_4", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_level_5", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_level_6", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_level_7", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_level_8", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_level_9", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id", name="uq_spell_slots_player"),
    )


def downgrade() -> None:
    op.drop_table("spell_slots")
    op.drop_table("inventory_items")
    for attr in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
        op.drop_column("players", attr)
