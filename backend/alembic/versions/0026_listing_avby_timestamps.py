"""Add avby published/renewed timestamps for feed ordering.

Revision ID: 0026_listing_avby_timestamps
Revises: 0025_avby_vin_fetches
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_listing_avby_timestamps"
down_revision: Union[str, None] = "0025_avby_vin_fetches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("car_listings", sa.Column("avby_published_at", sa.DateTime(), nullable=True))
    op.add_column("car_listings", sa.Column("avby_renewed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_car_listings_avby_published_at", "car_listings", ["avby_published_at"])
    op.create_index("ix_car_listings_avby_renewed_at", "car_listings", ["avby_renewed_at"])


def downgrade() -> None:
    op.drop_index("ix_car_listings_avby_renewed_at", table_name="car_listings")
    op.drop_index("ix_car_listings_avby_published_at", table_name="car_listings")
    op.drop_column("car_listings", "avby_renewed_at")
    op.drop_column("car_listings", "avby_published_at")
