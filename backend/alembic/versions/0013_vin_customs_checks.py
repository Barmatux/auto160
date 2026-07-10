"""Add vin_customs_checks cache table for GTK VIN lookups.

Revision ID: 0013_vin_customs_checks
Revises: 0012_avby_account_phone
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_vin_customs_checks"
down_revision: Union[str, None] = "0012_avby_account_phone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vin_customs_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vin", sa.String(length=17), nullable=False),
        sa.Column("database", sa.String(length=40), nullable=False),
        sa.Column("found", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("release_date", sa.String(length=64), nullable=True),
        sa.Column("raw_fields", sa.JSON(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vin", "database", name="uq_vin_customs_checks_vin_database"),
    )
    op.create_index("ix_vin_customs_checks_id", "vin_customs_checks", ["id"], unique=False)
    op.create_index("ix_vin_customs_checks_vin", "vin_customs_checks", ["vin"], unique=False)
    op.create_index("ix_vin_customs_checks_database", "vin_customs_checks", ["database"], unique=False)
    op.create_index("ix_vin_customs_checks_found", "vin_customs_checks", ["found"], unique=False)
    op.create_index("ix_vin_customs_checks_checked_at", "vin_customs_checks", ["checked_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_vin_customs_checks_checked_at", table_name="vin_customs_checks")
    op.drop_index("ix_vin_customs_checks_found", table_name="vin_customs_checks")
    op.drop_index("ix_vin_customs_checks_database", table_name="vin_customs_checks")
    op.drop_index("ix_vin_customs_checks_vin", table_name="vin_customs_checks")
    op.drop_index("ix_vin_customs_checks_id", table_name="vin_customs_checks")
    op.drop_table("vin_customs_checks")
