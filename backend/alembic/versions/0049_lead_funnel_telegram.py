"""Lead funnel fields and Telegram message links.

Revision ID: 0049_lead_funnel_telegram
Revises: 0048_site_lead_consent
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049_lead_funnel_telegram"
down_revision: Union[str, None] = "0048_site_lead_consent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "site_leads",
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
    )
    op.add_column("site_leads", sa.Column("deal_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("site_leads", sa.Column("deal_margin", sa.Numeric(14, 2), nullable=True))
    op.add_column("site_leads", sa.Column("deal_currency", sa.String(3), nullable=True))
    op.add_column("site_leads", sa.Column("manager_note", sa.Text(), nullable=True))
    op.add_column("site_leads", sa.Column("status_updated_at", sa.DateTime(), nullable=True))
    op.create_index("ix_site_leads_status", "site_leads", ["status"])
    # Leads already marked as read were handled by hand before the funnel existed.
    op.execute("UPDATE site_leads SET status = 'contacted' WHERE is_read = true")

    op.create_table(
        "telegram_message_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.String(40), nullable=False),
        sa.Column("tg_message_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("ref_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_telegram_message_links_id", "telegram_message_links", ["id"])
    op.create_index("ix_telegram_message_links_chat_id", "telegram_message_links", ["chat_id"])
    op.create_index(
        "ix_telegram_message_links_tg_message_id", "telegram_message_links", ["tg_message_id"]
    )


def downgrade() -> None:
    op.drop_table("telegram_message_links")
    op.drop_index("ix_site_leads_status", table_name="site_leads")
    for col in (
        "status_updated_at",
        "manager_note",
        "deal_currency",
        "deal_margin",
        "deal_amount",
        "status",
    ):
        op.drop_column("site_leads", col)
