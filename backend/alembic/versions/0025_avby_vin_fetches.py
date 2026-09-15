"""Add avby_vin_fetches for per-account daily VIN stats.

Revision ID: 0025_avby_vin_fetches
Revises: 0024_listing_source_external_id
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_avby_vin_fetches"
down_revision: Union[str, None] = "0024_listing_source_external_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avby_vin_fetches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("avby_service_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("car_listings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_avby_vin_fetches_account_id", "avby_vin_fetches", ["account_id"])
    op.create_index("ix_avby_vin_fetches_listing_id", "avby_vin_fetches", ["listing_id"])
    op.create_index("ix_avby_vin_fetches_created_at", "avby_vin_fetches", ["created_at"])
    op.create_index(
        "ix_avby_vin_fetches_account_created",
        "avby_vin_fetches",
        ["account_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_avby_vin_fetches_account_created", table_name="avby_vin_fetches")
    op.drop_index("ix_avby_vin_fetches_created_at", table_name="avby_vin_fetches")
    op.drop_index("ix_avby_vin_fetches_listing_id", table_name="avby_vin_fetches")
    op.drop_index("ix_avby_vin_fetches_account_id", table_name="avby_vin_fetches")
    op.drop_table("avby_vin_fetches")
