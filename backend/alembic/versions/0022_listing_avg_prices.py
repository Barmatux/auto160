"""Add listing_avg_prices for brand/model/year market averages (no UI yet)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_listing_avg_prices"
down_revision: Union[str, None] = "0021_catalog_gaps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "listing_avg_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("avg_price_byn", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_price_byn", sa.Numeric(12, 2), nullable=True),
        sa.Column("max_price_byn", sa.Numeric(12, 2), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_end", sa.DateTime(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("brand", "model", "year", name="uq_listing_avg_prices_brand_model_year"),
    )
    op.create_index("ix_listing_avg_prices_id", "listing_avg_prices", ["id"])
    op.create_index("ix_listing_avg_prices_brand", "listing_avg_prices", ["brand"])
    op.create_index("ix_listing_avg_prices_model", "listing_avg_prices", ["model"])
    op.create_index("ix_listing_avg_prices_year", "listing_avg_prices", ["year"])
    op.create_index("ix_listing_avg_prices_computed_at", "listing_avg_prices", ["computed_at"])


def downgrade() -> None:
    op.drop_index("ix_listing_avg_prices_computed_at", table_name="listing_avg_prices")
    op.drop_index("ix_listing_avg_prices_year", table_name="listing_avg_prices")
    op.drop_index("ix_listing_avg_prices_model", table_name="listing_avg_prices")
    op.drop_index("ix_listing_avg_prices_brand", table_name="listing_avg_prices")
    op.drop_index("ix_listing_avg_prices_id", table_name="listing_avg_prices")
    op.drop_table("listing_avg_prices")
