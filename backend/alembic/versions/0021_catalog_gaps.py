"""Add catalog_gaps queue for eu2 / internal match not_found."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_catalog_gaps"
down_revision: Union[str, None] = "0020_catalog_seats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_gaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="eu2"),
        sa.Column("external_ref", sa.String(length=120), nullable=True),
        sa.Column("make", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("generation", sa.String(length=120), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("body_type", sa.String(length=60), nullable=True),
        sa.Column("fuel_type", sa.String(length=30), nullable=True),
        sa.Column("engine_power_hp", sa.Integer(), nullable=True),
        sa.Column("engine_volume_l", sa.Numeric(4, 1), nullable=True),
        sa.Column("drivetrain", sa.String(length=30), nullable=True),
        sa.Column("transmission", sa.String(length=30), nullable=True),
        sa.Column("source_external_id", sa.String(length=120), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "resolved_catalog_item_id",
            sa.Integer(),
            sa.ForeignKey("catalog_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_catalog_gaps_id", "catalog_gaps", ["id"])
    op.create_index("ix_catalog_gaps_source", "catalog_gaps", ["source"])
    op.create_index("ix_catalog_gaps_external_ref", "catalog_gaps", ["external_ref"])
    op.create_index("ix_catalog_gaps_make", "catalog_gaps", ["make"])
    op.create_index("ix_catalog_gaps_model", "catalog_gaps", ["model"])
    op.create_index("ix_catalog_gaps_source_external_id", "catalog_gaps", ["source_external_id"])
    op.create_index("ix_catalog_gaps_status", "catalog_gaps", ["status"])
    op.create_index("ix_catalog_gaps_created_at", "catalog_gaps", ["created_at"])
    op.create_index("ix_catalog_gaps_resolved_catalog_item_id", "catalog_gaps", ["resolved_catalog_item_id"])


def downgrade() -> None:
    op.drop_index("ix_catalog_gaps_resolved_catalog_item_id", table_name="catalog_gaps")
    op.drop_index("ix_catalog_gaps_created_at", table_name="catalog_gaps")
    op.drop_index("ix_catalog_gaps_status", table_name="catalog_gaps")
    op.drop_index("ix_catalog_gaps_source_external_id", table_name="catalog_gaps")
    op.drop_index("ix_catalog_gaps_model", table_name="catalog_gaps")
    op.drop_index("ix_catalog_gaps_make", table_name="catalog_gaps")
    op.drop_index("ix_catalog_gaps_external_ref", table_name="catalog_gaps")
    op.drop_index("ix_catalog_gaps_source", table_name="catalog_gaps")
    op.drop_index("ix_catalog_gaps_id", table_name="catalog_gaps")
    op.drop_table("catalog_gaps")
