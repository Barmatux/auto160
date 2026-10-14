"""Store av.by ocenka / price-statistics analytics.

Revision ID: 0034_avby_price_stats
Revises: 0033_manual_vin_check_launches
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034_avby_price_stats"
down_revision: Union[str, None] = "0033_manual_vin_check_launches"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avby_price_stat_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("catalog_slug", sa.String(length=200), nullable=False),
        sa.Column("make", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("generation", sa.String(length=120), nullable=True),
        sa.Column("year_from", sa.Integer(), nullable=True),
        sa.Column("year_to", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("generation_id", sa.Integer(), nullable=True),
        sa.Column("resolve_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("resolve_error", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("catalog_slug", name="uq_avby_price_stat_targets_slug"),
    )
    op.create_index("ix_avby_price_stat_targets_catalog_slug", "avby_price_stat_targets", ["catalog_slug"])
    op.create_index("ix_avby_price_stat_targets_make", "avby_price_stat_targets", ["make"])
    op.create_index("ix_avby_price_stat_targets_model", "avby_price_stat_targets", ["model"])
    op.create_index("ix_avby_price_stat_targets_brand_id", "avby_price_stat_targets", ["brand_id"])
    op.create_index("ix_avby_price_stat_targets_model_id", "avby_price_stat_targets", ["model_id"])
    op.create_index("ix_avby_price_stat_targets_generation_id", "avby_price_stat_targets", ["generation_id"])
    op.create_index("ix_avby_price_stat_targets_resolve_status", "avby_price_stat_targets", ["resolve_status"])
    op.create_index("ix_avby_price_stat_targets_created_at", "avby_price_stat_targets", ["created_at"])

    op.create_table(
        "avby_price_year_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("target_id", sa.Integer(), sa.ForeignKey("avby_price_stat_targets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("generation_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("make", sa.String(length=80), nullable=True),
        sa.Column("model_name", sa.String(length=120), nullable=True),
        sa.Column("generation_name", sa.String(length=120), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("price_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_byn", sa.Numeric(12, 2), nullable=True),
        sa.Column("min_price_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("max_price_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("advert_count", sa.Integer(), nullable=True),
        sa.Column("active_advert_count", sa.Integer(), nullable=True),
        sa.Column("activity_new_60d", sa.Integer(), nullable=True),
        sa.Column("activity_removed_60d", sa.Integer(), nullable=True),
        sa.Column("activity_days", sa.Integer(), nullable=True),
        sa.Column("activity_by_month", sa.JSON(), nullable=True),
        sa.Column("main_filter_url", sa.String(length=1000), nullable=True),
        sa.Column("active_filter_url", sa.String(length=1000), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("active_payload", sa.JSON(), nullable=True),
        sa.Column("fetch_status", sa.String(length=20), nullable=False, server_default="ok"),
        sa.Column("fetch_error", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "brand_id",
            "model_id",
            "generation_id",
            "year",
            name="uq_avby_price_year_stats_ids_year",
        ),
    )
    op.create_index("ix_avby_price_year_stats_target_id", "avby_price_year_stats", ["target_id"])
    op.create_index("ix_avby_price_year_stats_brand_id", "avby_price_year_stats", ["brand_id"])
    op.create_index("ix_avby_price_year_stats_model_id", "avby_price_year_stats", ["model_id"])
    op.create_index("ix_avby_price_year_stats_generation_id", "avby_price_year_stats", ["generation_id"])
    op.create_index("ix_avby_price_year_stats_year", "avby_price_year_stats", ["year"])
    op.create_index("ix_avby_price_year_stats_fetch_status", "avby_price_year_stats", ["fetch_status"])
    op.create_index("ix_avby_price_year_stats_fetched_at", "avby_price_year_stats", ["fetched_at"])

    op.create_table(
        "avby_price_history_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year_stat_id", sa.Integer(), sa.ForeignKey("avby_price_year_stats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("median_price_usd", sa.Numeric(12, 2), nullable=True),
        sa.UniqueConstraint(
            "year_stat_id",
            "year",
            "month",
            name="uq_avby_price_history_points_stat_ym",
        ),
    )
    op.create_index("ix_avby_price_history_points_year_stat_id", "avby_price_history_points", ["year_stat_id"])
    op.create_index("ix_avby_price_history_points_year", "avby_price_history_points", ["year"])

    op.create_table(
        "avby_price_sold_adverts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year_stat_id", sa.Integer(), sa.ForeignKey("avby_price_year_stats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("avby_id", sa.Integer(), nullable=False),
        sa.Column("price_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_byn", sa.Numeric(12, 2), nullable=True),
        sa.Column("days_on_sale", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("public_status", sa.String(length=40), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.UniqueConstraint(
            "year_stat_id",
            "avby_id",
            name="uq_avby_price_sold_adverts_stat_avby",
        ),
    )
    op.create_index("ix_avby_price_sold_adverts_year_stat_id", "avby_price_sold_adverts", ["year_stat_id"])
    op.create_index("ix_avby_price_sold_adverts_avby_id", "avby_price_sold_adverts", ["avby_id"])


def downgrade() -> None:
    op.drop_table("avby_price_sold_adverts")
    op.drop_table("avby_price_history_points")
    op.drop_table("avby_price_year_stats")
    op.drop_table("avby_price_stat_targets")
