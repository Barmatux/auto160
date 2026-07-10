"""Add VIN field to car listings.

Revision ID: 0010_listing_vin
Revises: 0009_avby_vin_test_fields
Create Date: 2026-07-06 20:15:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_listing_vin"
down_revision: Union[str, None] = "0009_avby_vin_test_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("car_listings", sa.Column("vin", sa.String(length=17), nullable=True))
    op.add_column("car_listings", sa.Column("vin_fetched_at", sa.DateTime(), nullable=True))
    op.create_index("ix_car_listings_vin", "car_listings", ["vin"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_car_listings_vin", table_name="car_listings")
    op.drop_column("car_listings", "vin_fetched_at")
    op.drop_column("car_listings", "vin")
