"""Add phone login for av.by service accounts.

Revision ID: 0012_avby_account_phone
Revises: 0011_avby_refresh_token
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_avby_account_phone"
down_revision: Union[str, None] = "0011_avby_refresh_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("avby_service_accounts", sa.Column("phone", sa.String(length=20), nullable=True))
    op.alter_column("avby_service_accounts", "email", existing_type=sa.String(length=255), nullable=True)
    op.create_index("ix_avby_service_accounts_phone", "avby_service_accounts", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_avby_service_accounts_phone", table_name="avby_service_accounts")
    op.alter_column("avby_service_accounts", "email", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("avby_service_accounts", "phone")
