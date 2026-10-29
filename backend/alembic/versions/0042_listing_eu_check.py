"""Add EU check queue fields for ambiguous LT/EE listings.

Revision ID: 0042_listing_eu_check
Revises: 0041_listing_engine_type_len
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042_listing_eu_check"
down_revision: Union[str, None] = "0041_listing_engine_type_len"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "car_listings",
        sa.Column("eu_check_status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "car_listings",
        sa.Column("eu_check_reason", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_car_listings_eu_check_status",
        "car_listings",
        ["eu_check_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_car_listings_eu_check_status", table_name="car_listings")
    op.drop_column("car_listings", "eu_check_reason")
    op.drop_column("car_listings", "eu_check_status")
