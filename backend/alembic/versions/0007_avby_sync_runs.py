"""add avby sync run history table

Revision ID: 0007_avby_sync_runs
Revises: 0006_listing_avby_mapping_fields
Create Date: 2026-06-30 13:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_avby_sync_runs"
down_revision: Union[str, None] = "0006_listing_avby_mapping_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avby_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("trigger", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("models_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("brands_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_by_hp_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_brands_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pages_fetched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_hp", sa.Integer(), nullable=False, server_default="160"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_avby_sync_runs_id", "avby_sync_runs", ["id"], unique=False)
    op.create_index("ix_avby_sync_runs_started_at", "avby_sync_runs", ["started_at"], unique=False)
    op.create_index("ix_avby_sync_runs_status", "avby_sync_runs", ["status"], unique=False)
    op.create_index("ix_avby_sync_runs_trigger", "avby_sync_runs", ["trigger"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_avby_sync_runs_trigger", table_name="avby_sync_runs")
    op.drop_index("ix_avby_sync_runs_status", table_name="avby_sync_runs")
    op.drop_index("ix_avby_sync_runs_started_at", table_name="avby_sync_runs")
    op.drop_index("ix_avby_sync_runs_id", table_name="avby_sync_runs")
    op.drop_table("avby_sync_runs")
