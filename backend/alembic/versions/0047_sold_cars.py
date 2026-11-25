"""Sold cars archive imported from Excel (admin-only desk portal).

Revision ID: 0047_sold_cars
Revises: 0046_staff_role_source_key
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047_sold_cars"
down_revision: Union[str, None] = "0046_staff_role_source_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sold_partners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sold_partners_id", "sold_partners", ["id"])
    op.create_index("ix_sold_partners_code", "sold_partners", ["code"], unique=True)

    op.create_table(
        "sold_cars",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_key", sa.String(160), nullable=True),
        sa.Column("sheet", sa.String(120), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("sold_date", sa.Date(), nullable=True),
        sa.Column("sold_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("cost_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("commission", sa.Numeric(14, 2), nullable=True),
        sa.Column("profit", sa.Numeric(14, 2), nullable=True),
        sa.Column("fx_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("figures", sa.JSON(), nullable=False),
        sa.Column("sums", sa.JSON(), nullable=False),
        sa.Column("sheet_totals", sa.JSON(), nullable=True),
        sa.Column("raw_grid", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sold_cars_id", "sold_cars", ["id"])
    op.create_index("ix_sold_cars_source_key", "sold_cars", ["source_key"], unique=True)
    op.create_index("ix_sold_cars_title", "sold_cars", ["title"])
    op.create_index("ix_sold_cars_needs_review", "sold_cars", ["needs_review"])
    op.create_index("ix_sold_cars_created_at", "sold_cars", ["created_at"])
    op.create_index("ix_sold_cars_updated_at", "sold_cars", ["updated_at"])

    op.create_table(
        "sold_car_expenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("car_id", sa.Integer(), sa.ForeignKey("sold_cars.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("item", sa.String(300), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("payer_code", sa.String(40), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
    )
    op.create_index("ix_sold_car_expenses_id", "sold_car_expenses", ["id"])
    op.create_index("ix_sold_car_expenses_car_id", "sold_car_expenses", ["car_id"])
    op.create_index("ix_sold_car_expenses_payer_code", "sold_car_expenses", ["payer_code"])


def downgrade() -> None:
    op.drop_table("sold_car_expenses")
    op.drop_table("sold_cars")
    op.drop_table("sold_partners")
