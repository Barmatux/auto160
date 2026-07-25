"""Add catalog_item_id link on car listings.

Revision ID: 0016_listing_catalog_item_id
Revises: 0015_catalog_item_rating
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_listing_catalog_item_id"
down_revision: Union[str, None] = "0015_catalog_item_rating"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("car_listings", sa.Column("catalog_item_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_car_listings_catalog_item_id",
        "car_listings",
        "catalog_items",
        ["catalog_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_car_listings_catalog_item_id", "car_listings", ["catalog_item_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_car_listings_catalog_item_id", table_name="car_listings")
    op.drop_constraint("fk_car_listings_catalog_item_id", "car_listings", type_="foreignkey")
    op.drop_column("car_listings", "catalog_item_id")
