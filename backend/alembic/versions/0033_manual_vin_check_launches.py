"""Track which user launched each manual VIN check.

Revision ID: 0033_manual_vin_check_launches
Revises: 0032_manual_vin_checked_at
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_manual_vin_check_launches"
down_revision: Union[str, None] = "0032_manual_vin_checked_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "manual_vin_check_launches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("car_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("launched_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("listing_id", "user_id", name="uq_manual_vin_check_launches_listing_user"),
    )
    op.create_index("ix_manual_vin_check_launches_listing_id", "manual_vin_check_launches", ["listing_id"])
    op.create_index("ix_manual_vin_check_launches_user_id", "manual_vin_check_launches", ["user_id"])
    op.create_index("ix_manual_vin_check_launches_launched_at", "manual_vin_check_launches", ["launched_at"])


def downgrade() -> None:
    op.drop_index("ix_manual_vin_check_launches_launched_at", table_name="manual_vin_check_launches")
    op.drop_index("ix_manual_vin_check_launches_user_id", table_name="manual_vin_check_launches")
    op.drop_index("ix_manual_vin_check_launches_listing_id", table_name="manual_vin_check_launches")
    op.drop_table("manual_vin_check_launches")
