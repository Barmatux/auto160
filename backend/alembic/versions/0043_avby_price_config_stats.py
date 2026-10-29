"""Store av.by ocenka price stats per dropdown configuration.

Revision ID: 0043_avby_price_config_stats
Revises: 0042_listing_eu_check
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043_avby_price_config_stats"
down_revision: Union[str, None] = "0042_listing_eu_check"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avby_price_config_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "year_stat_id",
            sa.Integer(),
            sa.ForeignKey("avby_price_year_stats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engine_type_id", sa.Integer(), nullable=False),
        sa.Column("engine_type_label", sa.String(length=80), nullable=True),
        sa.Column("engine_capacity_id", sa.Integer(), nullable=False),
        sa.Column("engine_capacity_label", sa.String(length=80), nullable=True),
        sa.Column("transmission_type_id", sa.Integer(), nullable=False),
        sa.Column("transmission_type_label", sa.String(length=80), nullable=True),
        sa.Column("drive_type_id", sa.Integer(), nullable=False),
        sa.Column("drive_type_label", sa.String(length=80), nullable=True),
        sa.Column("price_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("price_byn", sa.Numeric(12, 2), nullable=True),
        sa.Column("min_price_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("max_price_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("advert_count", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("fetch_status", sa.String(length=20), nullable=False, server_default="ok"),
        sa.Column("fetch_error", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "year_stat_id",
            "engine_type_id",
            "engine_capacity_id",
            "transmission_type_id",
            "drive_type_id",
            name="uq_avby_price_config_stats_combo",
        ),
    )
    op.create_index("ix_avby_price_config_stats_year_stat_id", "avby_price_config_stats", ["year_stat_id"])
    op.create_index("ix_avby_price_config_stats_engine_type_id", "avby_price_config_stats", ["engine_type_id"])
    op.create_index(
        "ix_avby_price_config_stats_engine_capacity_id",
        "avby_price_config_stats",
        ["engine_capacity_id"],
    )
    op.create_index(
        "ix_avby_price_config_stats_transmission_type_id",
        "avby_price_config_stats",
        ["transmission_type_id"],
    )
    op.create_index("ix_avby_price_config_stats_drive_type_id", "avby_price_config_stats", ["drive_type_id"])
    op.create_index("ix_avby_price_config_stats_fetch_status", "avby_price_config_stats", ["fetch_status"])
    op.create_index("ix_avby_price_config_stats_fetched_at", "avby_price_config_stats", ["fetched_at"])


def downgrade() -> None:
    op.drop_index("ix_avby_price_config_stats_fetched_at", table_name="avby_price_config_stats")
    op.drop_index("ix_avby_price_config_stats_fetch_status", table_name="avby_price_config_stats")
    op.drop_index("ix_avby_price_config_stats_drive_type_id", table_name="avby_price_config_stats")
    op.drop_index("ix_avby_price_config_stats_transmission_type_id", table_name="avby_price_config_stats")
    op.drop_index("ix_avby_price_config_stats_engine_capacity_id", table_name="avby_price_config_stats")
    op.drop_index("ix_avby_price_config_stats_engine_type_id", table_name="avby_price_config_stats")
    op.drop_index("ix_avby_price_config_stats_year_stat_id", table_name="avby_price_config_stats")
    op.drop_table("avby_price_config_stats")
