"""Add manual_vin_checked_at for admin manual VIN checks.

Revision ID: 0032_manual_vin_checked_at
Revises: 0031_user_email_verification
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_manual_vin_checked_at"
down_revision: Union[str, None] = "0031_user_email_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("car_listings", sa.Column("manual_vin_checked_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_car_listings_manual_vin_checked_at",
        "car_listings",
        ["manual_vin_checked_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_car_listings_manual_vin_checked_at", table_name="car_listings")
    op.drop_column("car_listings", "manual_vin_checked_at")
