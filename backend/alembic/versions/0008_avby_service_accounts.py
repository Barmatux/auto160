"""add avby service accounts table

Revision ID: 0008_avby_service_accounts
Revises: 0007_avby_sync_runs
Create Date: 2026-07-04 17:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_avby_service_accounts"
down_revision: Union[str, None] = "0007_avby_sync_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "avby_service_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("mailtm_password", sa.String(length=255), nullable=True),
        sa.Column("avby_password", sa.String(length=255), nullable=True),
        sa.Column("api_key", sa.String(length=120), nullable=True),
        sa.Column("auth_token", sa.Text(), nullable=True),
        sa.Column("email_token", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("registered_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_avby_service_accounts_id", "avby_service_accounts", ["id"], unique=False)
    op.create_index("ix_avby_service_accounts_email", "avby_service_accounts", ["email"], unique=True)
    op.create_index("ix_avby_service_accounts_status", "avby_service_accounts", ["status"], unique=False)
    op.create_index("ix_avby_service_accounts_is_active", "avby_service_accounts", ["is_active"], unique=False)
    op.create_index("ix_avby_service_accounts_registered_at", "avby_service_accounts", ["registered_at"], unique=False)
    op.create_index("ix_avby_service_accounts_created_at", "avby_service_accounts", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_avby_service_accounts_created_at", table_name="avby_service_accounts")
    op.drop_index("ix_avby_service_accounts_registered_at", table_name="avby_service_accounts")
    op.drop_index("ix_avby_service_accounts_is_active", table_name="avby_service_accounts")
    op.drop_index("ix_avby_service_accounts_status", table_name="avby_service_accounts")
    op.drop_index("ix_avby_service_accounts_email", table_name="avby_service_accounts")
    op.drop_index("ix_avby_service_accounts_id", table_name="avby_service_accounts")
    op.drop_table("avby_service_accounts")
