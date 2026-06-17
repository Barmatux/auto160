"""add catalog item photos table

Revision ID: 0003_catalog_item_photos
Revises: 0002_catalog_items
Create Date: 2026-06-10 18:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_catalog_item_photos"
down_revision: Union[str, None] = "0002_catalog_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_item_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("catalog_item_id", sa.Integer(), sa.ForeignKey("catalog_items.id"), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_cover", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_catalog_item_photos_id", "catalog_item_photos", ["id"], unique=False)
    op.create_index("ix_catalog_item_photos_catalog_item_id", "catalog_item_photos", ["catalog_item_id"], unique=False)
    op.create_index("ix_catalog_item_photos_storage_key", "catalog_item_photos", ["storage_key"], unique=True)
    op.create_index("ix_catalog_item_photos_sort_order", "catalog_item_photos", ["sort_order"], unique=False)
    op.create_index("ix_catalog_item_photos_is_cover", "catalog_item_photos", ["is_cover"], unique=False)
    op.create_index("ix_catalog_item_photos_created_at", "catalog_item_photos", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_catalog_item_photos_created_at", table_name="catalog_item_photos")
    op.drop_index("ix_catalog_item_photos_is_cover", table_name="catalog_item_photos")
    op.drop_index("ix_catalog_item_photos_sort_order", table_name="catalog_item_photos")
    op.drop_index("ix_catalog_item_photos_storage_key", table_name="catalog_item_photos")
    op.drop_index("ix_catalog_item_photos_catalog_item_id", table_name="catalog_item_photos")
    op.drop_index("ix_catalog_item_photos_id", table_name="catalog_item_photos")
    op.drop_table("catalog_item_photos")
