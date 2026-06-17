"""add hybrid spec fields to catalog items

Revision ID: 0005_catalog_item_hybrid_specs
Revises: 0004_add_username_to_users
Create Date: 2026-06-11 14:58:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_catalog_item_hybrid_specs"
down_revision: Union[str, None] = "0004_add_username_to_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("catalog_items", sa.Column("source_site", sa.String(length=40), nullable=True))
    op.add_column("catalog_items", sa.Column("source_url", sa.String(length=500), nullable=True))
    op.add_column("catalog_items", sa.Column("source_external_id", sa.String(length=120), nullable=True))
    op.add_column("catalog_items", sa.Column("raw_specs", sa.JSON(), nullable=True))

    op.create_index("ix_catalog_items_source_site", "catalog_items", ["source_site"], unique=False)
    op.create_index("ix_catalog_items_source_external_id", "catalog_items", ["source_external_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_catalog_items_source_external_id", table_name="catalog_items")
    op.drop_index("ix_catalog_items_source_site", table_name="catalog_items")
    op.drop_column("catalog_items", "raw_specs")
    op.drop_column("catalog_items", "source_external_id")
    op.drop_column("catalog_items", "source_url")
    op.drop_column("catalog_items", "source_site")
