"""Add email verification fields on users.

Revision ID: 0031_user_email_verification
Revises: 0030_manager_messages
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_user_email_verification"
down_revision: Union[str, None] = "0030_manager_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("email_verify_token_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("email_verify_sent_at", sa.DateTime(), nullable=True))
    op.create_index("ix_users_email_verified_at", "users", ["email_verified_at"])
    op.create_index("ix_users_email_verify_token_hash", "users", ["email_verify_token_hash"])
    # Existing accounts stay usable (hard gate must not lock production admins).
    op.execute("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")


def downgrade() -> None:
    op.drop_index("ix_users_email_verify_token_hash", table_name="users")
    op.drop_index("ix_users_email_verified_at", table_name="users")
    op.drop_column("users", "email_verify_sent_at")
    op.drop_column("users", "email_verify_token_hash")
    op.drop_column("users", "email_verified_at")
