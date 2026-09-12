"""Add window_days to listing_avg_prices unique key and outlier stats columns.

Revision ID: 0023_listing_avg_windows
Revises: 0022_listing_avg_prices
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_listing_avg_windows"
down_revision: Union[str, None] = "0022_listing_avg_prices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_listing_avg_prices_brand_model_year", "listing_avg_prices", type_="unique")
    op.add_column(
        "listing_avg_prices",
        sa.Column("sample_count_raw", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "listing_avg_prices",
        sa.Column("outliers_removed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_unique_constraint(
        "uq_listing_avg_prices_brand_model_year_window",
        "listing_avg_prices",
        ["brand", "model", "year", "window_days"],
    )
    op.create_index("ix_listing_avg_prices_window_days", "listing_avg_prices", ["window_days"])


def downgrade() -> None:
    op.drop_index("ix_listing_avg_prices_window_days", table_name="listing_avg_prices")
    op.drop_constraint("uq_listing_avg_prices_brand_model_year_window", "listing_avg_prices", type_="unique")
    op.drop_column("listing_avg_prices", "outliers_removed")
    op.drop_column("listing_avg_prices", "sample_count_raw")
    op.create_unique_constraint(
        "uq_listing_avg_prices_brand_model_year",
        "listing_avg_prices",
        ["brand", "model", "year"],
    )
