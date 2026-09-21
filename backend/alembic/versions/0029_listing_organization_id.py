"""Add organization_id to car_listings for av.by business sellers.

Revision ID: 0029_listing_organization_id
Revises: 0028_rag_chunks_chat
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_listing_organization_id"
down_revision: Union[str, None] = "0028_rag_chunks_chat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("car_listings", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_index("ix_car_listings_organization_id", "car_listings", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_car_listings_organization_id", table_name="car_listings")
    op.drop_column("car_listings", "organization_id")
