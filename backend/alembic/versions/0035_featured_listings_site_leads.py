"""Featured homepage listings and public site leads.

Revision ID: 0035_featured_listings_site_leads
Revises: 0034_avby_price_stats
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035_featured_listings_site_leads"
down_revision: Union[str, None] = "0034_avby_price_stats"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "featured_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("sort_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["car_listings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("listing_id", name="uq_featured_listings_listing_id"),
    )
    op.create_index("ix_featured_listings_listing_id", "featured_listings", ["listing_id"])
    op.create_index("ix_featured_listings_sort_weight", "featured_listings", ["sort_weight"])
    op.create_index("ix_featured_listings_is_active", "featured_listings", ["is_active"])
    op.create_index("ix_featured_listings_created_at", "featured_listings", ["created_at"])

    op.create_table(
        "site_leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("contact_name", sa.String(length=120), nullable=False),
        sa.Column("contact", sa.String(length=120), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("listing_id", sa.Integer(), nullable=True),
        sa.Column("avby_url", sa.String(length=500), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["listing_id"], ["car_listings.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_site_leads_source", "site_leads", ["source"])
    op.create_index("ix_site_leads_listing_id", "site_leads", ["listing_id"])
    op.create_index("ix_site_leads_is_read", "site_leads", ["is_read"])
    op.create_index("ix_site_leads_created_at", "site_leads", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_site_leads_created_at", table_name="site_leads")
    op.drop_index("ix_site_leads_is_read", table_name="site_leads")
    op.drop_index("ix_site_leads_listing_id", table_name="site_leads")
    op.drop_index("ix_site_leads_source", table_name="site_leads")
    op.drop_table("site_leads")
    op.drop_index("ix_featured_listings_created_at", table_name="featured_listings")
    op.drop_index("ix_featured_listings_is_active", table_name="featured_listings")
    op.drop_index("ix_featured_listings_sort_weight", table_name="featured_listings")
    op.drop_index("ix_featured_listings_listing_id", table_name="featured_listings")
    op.drop_table("featured_listings")
