"""add vin test fields to avby service accounts

Revision ID: 0009_avby_vin_test_fields
Revises: 0008_avby_service_accounts
Create Date: 2026-07-06 19:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_avby_vin_test_fields"
down_revision: Union[str, None] = "0008_avby_service_accounts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "avby_service_accounts",
        sa.Column("purpose", sa.String(length=30), nullable=False, server_default="parser"),
    )
    op.add_column("avby_service_accounts", sa.Column("daily_vin_limit", sa.Integer(), nullable=True))
    op.add_column(
        "avby_service_accounts",
        sa.Column("vin_checks_today", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("avby_service_accounts", sa.Column("vin_checks_day", sa.Date(), nullable=True))
    op.create_index("ix_avby_service_accounts_purpose", "avby_service_accounts", ["purpose"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_avby_service_accounts_purpose", table_name="avby_service_accounts")
    op.drop_column("avby_service_accounts", "vin_checks_day")
    op.drop_column("avby_service_accounts", "vin_checks_today")
    op.drop_column("avby_service_accounts", "daily_vin_limit")
    op.drop_column("avby_service_accounts", "purpose")
