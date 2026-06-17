"""add catalog items table

Revision ID: 0002_catalog_items
Revises: 0001_initial_schema
Create Date: 2026-06-10 17:52:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_catalog_items"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("make", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("generation", sa.String(length=120), nullable=True),
        sa.Column("year_from", sa.Integer(), nullable=True),
        sa.Column("year_to", sa.Integer(), nullable=True),
        sa.Column("min_price_rub", sa.Numeric(12, 2), nullable=True),
        sa.Column("body_type", sa.String(length=60), nullable=True),
        sa.Column("export_country", sa.String(length=80), nullable=True),
        sa.Column("steering_wheel", sa.String(length=30), nullable=True),
        sa.Column("fuel_type", sa.String(length=30), nullable=True),
        sa.Column("engine_power_hp", sa.Integer(), nullable=True),
        sa.Column("engine_volume_l", sa.Numeric(4, 1), nullable=True),
        sa.Column("drivetrain", sa.String(length=30), nullable=True),
        sa.Column("transmission", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_catalog_items_id", "catalog_items", ["id"], unique=False)
    op.create_index("ix_catalog_items_make", "catalog_items", ["make"], unique=False)
    op.create_index("ix_catalog_items_model", "catalog_items", ["model"], unique=False)
    op.create_index("ix_catalog_items_year_from", "catalog_items", ["year_from"], unique=False)
    op.create_index("ix_catalog_items_year_to", "catalog_items", ["year_to"], unique=False)
    op.create_index("ix_catalog_items_min_price_rub", "catalog_items", ["min_price_rub"], unique=False)
    op.create_index("ix_catalog_items_body_type", "catalog_items", ["body_type"], unique=False)
    op.create_index("ix_catalog_items_export_country", "catalog_items", ["export_country"], unique=False)
    op.create_index("ix_catalog_items_fuel_type", "catalog_items", ["fuel_type"], unique=False)
    op.create_index("ix_catalog_items_created_at", "catalog_items", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_catalog_items_created_at", table_name="catalog_items")
    op.drop_index("ix_catalog_items_fuel_type", table_name="catalog_items")
    op.drop_index("ix_catalog_items_export_country", table_name="catalog_items")
    op.drop_index("ix_catalog_items_body_type", table_name="catalog_items")
    op.drop_index("ix_catalog_items_min_price_rub", table_name="catalog_items")
    op.drop_index("ix_catalog_items_year_to", table_name="catalog_items")
    op.drop_index("ix_catalog_items_year_from", table_name="catalog_items")
    op.drop_index("ix_catalog_items_model", table_name="catalog_items")
    op.drop_index("ix_catalog_items_make", table_name="catalog_items")
    op.drop_index("ix_catalog_items_id", table_name="catalog_items")
    op.drop_table("catalog_items")
