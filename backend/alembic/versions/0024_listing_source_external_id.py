"""Add source + external_id to car_listings for multi-source imports.

Revision ID: 0024_listing_source_external_id
Revises: 0023_listing_avg_windows
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_listing_source_external_id"
down_revision: Union[str, None] = "0023_listing_avg_windows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("car_listings", sa.Column("source", sa.String(length=40), nullable=True))
    op.add_column("car_listings", sa.Column("external_id", sa.String(length=120), nullable=True))
    op.create_index("ix_car_listings_source", "car_listings", ["source"])
    op.create_index("ix_car_listings_external_id", "car_listings", ["external_id"])
    op.create_unique_constraint(
        "uq_car_listings_source_external_id",
        "car_listings",
        ["source", "external_id"],
    )
    op.execute(
        """
        UPDATE car_listings
        SET source = 'av.by',
            external_id = CAST(avby_id AS TEXT)
        WHERE avby_id IS NOT NULL
          AND (source IS NULL OR external_id IS NULL)
        """
    )


def downgrade() -> None:
    op.drop_constraint("uq_car_listings_source_external_id", "car_listings", type_="unique")
    op.drop_index("ix_car_listings_external_id", table_name="car_listings")
    op.drop_index("ix_car_listings_source", table_name="car_listings")
    op.drop_column("car_listings", "external_id")
    op.drop_column("car_listings", "source")
