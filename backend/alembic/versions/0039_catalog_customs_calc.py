"""Add customs_calc flag to catalog_items for calculator dropdowns.

Revision ID: 0039_catalog_customs_calc
Revises: 0038_customs_db_hierarchy
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039_catalog_customs_calc"
down_revision: Union[str, None] = "0038_customs_db_hierarchy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("customs_calc", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(
        "ix_catalog_items_customs_calc",
        "catalog_items",
        ["customs_calc"],
    )
    op.alter_column("catalog_items", "customs_calc", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_catalog_items_customs_calc", table_name="catalog_items")
    op.drop_column("catalog_items", "customs_calc")
