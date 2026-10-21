"""Add arbitrage_track flag to catalog_items for EU→BY analytics.

Revision ID: 0036_catalog_arbitrage_track
Revises: 0035_featured_site_leads
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036_catalog_arbitrage_track"
down_revision: Union[str, None] = "0035_featured_site_leads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("arbitrage_track", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_catalog_items_arbitrage_track",
        "catalog_items",
        ["arbitrage_track"],
        unique=False,
    )
    op.alter_column("catalog_items", "arbitrage_track", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_catalog_items_arbitrage_track", table_name="catalog_items")
    op.drop_column("catalog_items", "arbitrage_track")
