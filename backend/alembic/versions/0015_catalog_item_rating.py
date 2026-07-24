"""Add rating column to catalog_items for internal ranking.

Revision ID: 0015_catalog_item_rating
Revises: 0014_site_events
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_catalog_item_rating"
down_revision: Union[str, None] = "0014_site_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("catalog_items", sa.Column("rating", sa.Numeric(precision=6, scale=2), nullable=True))
    op.create_index("ix_catalog_items_rating", "catalog_items", ["rating"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_catalog_items_rating", table_name="catalog_items")
    op.drop_column("catalog_items", "rating")
