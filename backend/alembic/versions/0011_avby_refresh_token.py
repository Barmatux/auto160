"""add refresh_token to avby service accounts

Revision ID: 0011_avby_refresh_token
Revises: 0010_listing_vin
Create Date: 2026-07-06 22:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_avby_refresh_token"
down_revision: Union[str, None] = "0010_listing_vin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("avby_service_accounts", sa.Column("refresh_token", sa.Text(), nullable=True))
    op.add_column("avby_service_accounts", sa.Column("auth_token_expires_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("avby_service_accounts", "auth_token_expires_at")
    op.drop_column("avby_service_accounts", "refresh_token")
