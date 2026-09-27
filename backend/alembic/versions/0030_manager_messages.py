"""Add message_threads and messages for manager messenger.

Revision ID: 0030_manager_messages
Revises: 0029_listing_organization_id
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030_manager_messages"
down_revision: Union[str, None] = "0029_listing_organization_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "message_threads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), sa.ForeignKey("car_listings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("guest_token", sa.String(length=64), nullable=True),
        sa.Column("contact_name", sa.String(length=120), nullable=False),
        sa.Column("contact_phone", sa.String(length=40), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "closed", name="messagethreadstatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("visitor_last_read_at", sa.DateTime(), nullable=True),
        sa.Column("manager_last_read_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_message_threads_id", "message_threads", ["id"])
    op.create_index("ix_message_threads_listing_id", "message_threads", ["listing_id"])
    op.create_index("ix_message_threads_user_id", "message_threads", ["user_id"])
    op.create_index("ix_message_threads_guest_token", "message_threads", ["guest_token"])
    op.create_index("ix_message_threads_status", "message_threads", ["status"])
    op.create_index("ix_message_threads_last_message_at", "message_threads", ["last_message_at"])
    op.create_index("ix_message_threads_created_at", "message_threads", ["created_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("thread_id", sa.Integer(), sa.ForeignKey("message_threads.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "sender",
            sa.Enum("visitor", "manager", name="messagesender"),
            nullable=False,
        ),
        sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_messages_id", "messages", ["id"])
    op.create_index("ix_messages_thread_id", "messages", ["thread_id"])
    op.create_index("ix_messages_sender", "messages", ["sender"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_sender", table_name="messages")
    op.drop_index("ix_messages_thread_id", table_name="messages")
    op.drop_index("ix_messages_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_message_threads_created_at", table_name="message_threads")
    op.drop_index("ix_message_threads_last_message_at", table_name="message_threads")
    op.drop_index("ix_message_threads_status", table_name="message_threads")
    op.drop_index("ix_message_threads_guest_token", table_name="message_threads")
    op.drop_index("ix_message_threads_user_id", table_name="message_threads")
    op.drop_index("ix_message_threads_listing_id", table_name="message_threads")
    op.drop_index("ix_message_threads_id", table_name="message_threads")
    op.drop_table("message_threads")
    op.execute("DROP TYPE IF EXISTS messagesender")
    op.execute("DROP TYPE IF EXISTS messagethreadstatus")
