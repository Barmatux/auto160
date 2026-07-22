"""Add site_events table for analytics and activity log.

Revision ID: 0014_site_events
Revises: 0013_vin_customs_checks
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_site_events"
down_revision: Union[str, None] = "0013_vin_customs_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "site_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("query_string", sa.String(length=500), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("referrer", sa.String(length=500), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_site_events_id", "site_events", ["id"], unique=False)
    op.create_index("ix_site_events_event_type", "site_events", ["event_type"], unique=False)
    op.create_index("ix_site_events_path", "site_events", ["path"], unique=False)
    op.create_index("ix_site_events_user_id", "site_events", ["user_id"], unique=False)
    op.create_index("ix_site_events_session_id", "site_events", ["session_id"], unique=False)
    op.create_index("ix_site_events_created_at", "site_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_site_events_created_at", table_name="site_events")
    op.drop_index("ix_site_events_session_id", table_name="site_events")
    op.drop_index("ix_site_events_user_id", table_name="site_events")
    op.drop_index("ix_site_events_path", table_name="site_events")
    op.drop_index("ix_site_events_event_type", table_name="site_events")
    op.drop_index("ix_site_events_id", table_name="site_events")
    op.drop_table("site_events")
