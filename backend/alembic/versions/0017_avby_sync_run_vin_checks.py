"""Add per-listing VIN check log for av.by sync runs.

Revision ID: 0017_avby_sync_run_vin_checks
Revises: 0016_listing_catalog_item_id
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_avby_sync_run_vin_checks"
down_revision: Union[str, None] = "0016_listing_catalog_item_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avby_sync_run_vin_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sync_run_id", sa.Integer(), sa.ForeignKey("avby_sync_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("car_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phase", sa.String(length=20), nullable=False),
        sa.Column("vin_obtained", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vin", sa.String(length=17), nullable=True),
        sa.Column("vin_indicated", sa.Boolean(), nullable=True),
        sa.Column("customs_checked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("customs_found", sa.Boolean(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_avby_sync_run_vin_checks_sync_run_id", "avby_sync_run_vin_checks", ["sync_run_id"])
    op.create_index("ix_avby_sync_run_vin_checks_listing_id", "avby_sync_run_vin_checks", ["listing_id"])
    op.create_index("ix_avby_sync_run_vin_checks_phase", "avby_sync_run_vin_checks", ["phase"])
    op.create_index("ix_avby_sync_run_vin_checks_created_at", "avby_sync_run_vin_checks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_avby_sync_run_vin_checks_created_at", table_name="avby_sync_run_vin_checks")
    op.drop_index("ix_avby_sync_run_vin_checks_phase", table_name="avby_sync_run_vin_checks")
    op.drop_index("ix_avby_sync_run_vin_checks_listing_id", table_name="avby_sync_run_vin_checks")
    op.drop_index("ix_avby_sync_run_vin_checks_sync_run_id", table_name="avby_sync_run_vin_checks")
    op.drop_table("avby_sync_run_vin_checks")
