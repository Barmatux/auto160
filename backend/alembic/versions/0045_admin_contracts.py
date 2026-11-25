"""Admin contracts archive for Scandi Motors docs printer.

Revision ID: 0045_admin_contracts
Revises: 0044_blog_posts
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045_admin_contracts"
down_revision: Union[str, None] = "0044_blog_posts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_contracts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_number", sa.String(80), nullable=True),
        sa.Column("client_name", sa.String(300), nullable=True),
        sa.Column("amount", sa.String(40), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_admin_contracts_contract_number", "admin_contracts", ["contract_number"])
    op.create_index("ix_admin_contracts_client_name", "admin_contracts", ["client_name"])
    op.create_index("ix_admin_contracts_created_by_id", "admin_contracts", ["created_by_id"])
    op.create_index("ix_admin_contracts_created_at", "admin_contracts", ["created_at"])
    op.create_index("ix_admin_contracts_updated_at", "admin_contracts", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_contracts_updated_at", table_name="admin_contracts")
    op.drop_index("ix_admin_contracts_created_at", table_name="admin_contracts")
    op.drop_index("ix_admin_contracts_created_by_id", table_name="admin_contracts")
    op.drop_index("ix_admin_contracts_client_name", table_name="admin_contracts")
    op.drop_index("ix_admin_contracts_contract_number", table_name="admin_contracts")
    op.drop_table("admin_contracts")
