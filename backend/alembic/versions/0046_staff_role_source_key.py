"""Add staff user role and contract source_key for Supabase import.

Revision ID: 0046_staff_role_source_key
Revises: 0045_admin_contracts
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "0046_staff_role_source_key"
down_revision: Union[str, None] = "0045_admin_contracts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Postgres forbids ALTER TYPE ... ADD VALUE inside a transaction.
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'staff'"))

    inspector = inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("admin_contracts")}
    if "source_key" not in columns:
        op.add_column(
            "admin_contracts",
            sa.Column("source_key", sa.String(length=80), nullable=True),
        )

    indexes = {ix["name"] for ix in inspector.get_indexes("admin_contracts")}
    if "ix_admin_contracts_source_key" not in indexes:
        op.create_index(
            "ix_admin_contracts_source_key",
            "admin_contracts",
            ["source_key"],
            unique=True,
        )


def downgrade() -> None:
    op.drop_index("ix_admin_contracts_source_key", table_name="admin_contracts")
    op.drop_column("admin_contracts", "source_key")
    # Postgres enum values cannot be removed safely; leave 'staff' in place.
