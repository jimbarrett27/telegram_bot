"""Add zones, zone_adjacencies, and zone_entities tables for spatial tracking

Revision ID: 006
Revises: 005
Create Date: 2026-02-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "zones",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "name", name="uq_zone_game_name"),
    )
    op.create_index("idx_zones_game_id", "zones", ["game_id"])

    op.create_table(
        "zone_adjacencies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("zone_a_id", sa.Integer(), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("zone_b_id", sa.Integer(), sa.ForeignKey("zones.id"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zone_a_id", "zone_b_id", name="uq_zone_adjacency"),
    )
    op.create_index("idx_zone_adj_a", "zone_adjacencies", ["zone_a_id"])
    op.create_index("idx_zone_adj_b", "zone_adjacencies", ["zone_b_id"])

    op.create_table(
        "zone_entities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("zone_id", sa.Integer(), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("game_id", sa.Integer(), sa.ForeignKey("games.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id"), nullable=True),
        sa.Column("entity_type", sa.Text(), nullable=False, server_default="npc"),
        sa.Column("created_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_zone_entities_zone_id", "zone_entities", ["zone_id"])
    op.create_index("idx_zone_entities_game_id", "zone_entities", ["game_id"])


def downgrade() -> None:
    op.drop_table("zone_entities")
    op.drop_table("zone_adjacencies")
    op.drop_table("zones")
