"""Customs calculator vehicle specs catalog (admin «Растаможка»).

Revision ID: 0037_customs_vehicle_specs
Revises: 0036_catalog_arbitrage_track
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037_customs_vehicle_specs"
down_revision: Union[str, None] = "0036_catalog_arbitrage_track"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customs_vehicle_specs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("make", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("generation", sa.String(length=120), nullable=True),
        sa.Column("year_from", sa.Integer(), nullable=True),
        sa.Column("year_to", sa.Integer(), nullable=True),
        sa.Column("engine_cc", sa.Integer(), nullable=False),
        sa.Column("power_hp", sa.Float(), nullable=False),
        sa.Column("engine_kind", sa.String(length=20), nullable=False, server_default="ice"),
        sa.Column("fuel_label", sa.String(length=40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_customs_vehicle_specs_make", "customs_vehicle_specs", ["make"])
    op.create_index("ix_customs_vehicle_specs_model", "customs_vehicle_specs", ["model"])
    op.create_index("ix_customs_vehicle_specs_is_active", "customs_vehicle_specs", ["is_active"])
    op.create_index("ix_customs_vehicle_specs_sort_weight", "customs_vehicle_specs", ["sort_weight"])


def downgrade() -> None:
    op.drop_index("ix_customs_vehicle_specs_sort_weight", table_name="customs_vehicle_specs")
    op.drop_index("ix_customs_vehicle_specs_is_active", table_name="customs_vehicle_specs")
    op.drop_index("ix_customs_vehicle_specs_model", table_name="customs_vehicle_specs")
    op.drop_index("ix_customs_vehicle_specs_make", table_name="customs_vehicle_specs")
    op.drop_table("customs_vehicle_specs")
