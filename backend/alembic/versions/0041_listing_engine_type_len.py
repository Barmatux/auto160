"""Widen car_listings.engine_type for long hybrid fuel labels.

Revision ID: 0041_listing_engine_type_len
Revises: 0040_catalog_engine_capacity_cc
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041_listing_engine_type_len"
down_revision: Union[str, None] = "0040_catalog_engine_capacity_cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "car_listings",
        "engine_type",
        existing_type=sa.String(length=40),
        type_=sa.String(length=80),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "car_listings",
        "engine_type",
        existing_type=sa.String(length=80),
        type_=sa.String(length=40),
        existing_nullable=True,
    )
