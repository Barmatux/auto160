"""Listing price BYN flag and nullable price for av.by imports without BYN."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_listing_price_byn_missing"
down_revision: Union[str, None] = "0018_catalog_hidden"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "car_listings",
        sa.Column("price_byn_missing", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_car_listings_price_byn_missing",
        "car_listings",
        ["price_byn_missing"],
        unique=False,
    )
    op.alter_column("car_listings", "price", existing_type=sa.Numeric(12, 2), nullable=True)
    op.alter_column("car_listings", "price_byn_missing", server_default=None)


def downgrade() -> None:
    op.alter_column("car_listings", "price", existing_type=sa.Numeric(12, 2), nullable=False)
    op.drop_index("ix_car_listings_price_byn_missing", table_name="car_listings")
    op.drop_column("car_listings", "price_byn_missing")
