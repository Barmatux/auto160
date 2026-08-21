"""Add hidden_from_catalog flag to catalog_items.

Revision ID: 0018_catalog_item_hidden_from_catalog
Revises: 0017_avby_sync_run_vin_checks
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_catalog_item_hidden_from_catalog"
down_revision: Union[str, None] = "0017_avby_sync_run_vin_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("hidden_from_catalog", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_catalog_items_hidden_from_catalog",
        "catalog_items",
        ["hidden_from_catalog"],
        unique=False,
    )
    op.alter_column("catalog_items", "hidden_from_catalog", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_catalog_items_hidden_from_catalog", table_name="catalog_items")
    op.drop_column("catalog_items", "hidden_from_catalog")
