"""BCA auction lots and their documents.

Revision ID: 0049_bca_auctions
Revises: 0048_site_lead_consent
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0049_bca_auctions"
down_revision: Union[str, None] = "0048_site_lead_consent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bca_auctions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sale_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(300), nullable=False, server_default=""),
        sa.Column("country", sa.String(8), nullable=False, server_default=""),
        sa.Column("sale_type", sa.String(160), nullable=False, server_default=""),
        sa.Column("channel", sa.String(40), nullable=False, server_default=""),
        sa.Column("location", sa.String(160), nullable=False, server_default=""),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("catalogue_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("section_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("lot_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("can_view_pricing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bca_auctions_sale_id", "bca_auctions", ["sale_id"], unique=True)
    op.create_index("ix_bca_auctions_country", "bca_auctions", ["country"])
    op.create_index("ix_bca_auctions_starts_at", "bca_auctions", ["starts_at"])
    op.create_index("ix_bca_auctions_last_seen_at", "bca_auctions", ["last_seen_at"])

    op.create_table(
        "bca_lots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auction_id", sa.Integer(), sa.ForeignKey("bca_auctions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_id", sa.String(64), nullable=False),
        sa.Column("lot_id", sa.String(32), nullable=False, server_default=""),
        sa.Column("lot_number", sa.String(32), nullable=False, server_default=""),
        sa.Column("lot_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("headline", sa.Text(), nullable=False, server_default=""),
        sa.Column("make", sa.String(80), nullable=False, server_default=""),
        sa.Column("model", sa.String(80), nullable=False, server_default=""),
        sa.Column("derivative", sa.String(160), nullable=False, server_default=""),
        sa.Column("vin", sa.String(32), nullable=False, server_default=""),
        sa.Column("mileage_km", sa.Integer(), nullable=True),
        sa.Column("registration", sa.String(32), nullable=False, server_default=""),
        sa.Column("registration_date", sa.String(40), nullable=False, server_default=""),
        sa.Column("fuel_type", sa.String(40), nullable=False, server_default=""),
        sa.Column("power_kw", sa.Integer(), nullable=True),
        sa.Column("power_ps", sa.Integer(), nullable=True),
        sa.Column("sale_location", sa.String(160), nullable=False, server_default=""),
        sa.Column("vehicle_location", sa.String(160), nullable=False, server_default=""),
        sa.Column("image_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("photo_s3_key", sa.Text(), nullable=False, server_default=""),
        sa.Column("bid_now", sa.String(80), nullable=False, server_default=""),
        sa.Column("buy_now", sa.String(80), nullable=False, server_default=""),
        sa.Column("condition_report_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("mechanical_report_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bca_lots_auction_id", "bca_lots", ["auction_id"])
    op.create_index("ix_bca_lots_vehicle_id", "bca_lots", ["vehicle_id"], unique=True)
    op.create_index("ix_bca_lots_lot_id", "bca_lots", ["lot_id"])
    op.create_index("ix_bca_lots_make", "bca_lots", ["make"])
    op.create_index("ix_bca_lots_vin", "bca_lots", ["vin"])

    op.create_table(
        "bca_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auction_id", sa.Integer(), sa.ForeignKey("bca_auctions.id", ondelete="CASCADE"), nullable=True),
        sa.Column("lot_pk", sa.Integer(), sa.ForeignKey("bca_lots.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("kind", "source_url", name="uq_bca_documents_kind_url"),
    )
    op.create_index("ix_bca_documents_auction_id", "bca_documents", ["auction_id"])
    op.create_index("ix_bca_documents_lot_pk", "bca_documents", ["lot_pk"])
    op.create_index("ix_bca_documents_status", "bca_documents", ["status"])


def downgrade() -> None:
    op.drop_index("ix_bca_documents_status", table_name="bca_documents")
    op.drop_index("ix_bca_documents_lot_pk", table_name="bca_documents")
    op.drop_index("ix_bca_documents_auction_id", table_name="bca_documents")
    op.drop_table("bca_documents")
    op.drop_index("ix_bca_lots_vin", table_name="bca_lots")
    op.drop_index("ix_bca_lots_make", table_name="bca_lots")
    op.drop_index("ix_bca_lots_lot_id", table_name="bca_lots")
    op.drop_index("ix_bca_lots_vehicle_id", table_name="bca_lots")
    op.drop_index("ix_bca_lots_auction_id", table_name="bca_lots")
    op.drop_table("bca_lots")
    op.drop_index("ix_bca_auctions_last_seen_at", table_name="bca_auctions")
    op.drop_index("ix_bca_auctions_starts_at", table_name="bca_auctions")
    op.drop_index("ix_bca_auctions_country", table_name="bca_auctions")
    op.drop_index("ix_bca_auctions_sale_id", table_name="bca_auctions")
    op.drop_table("bca_auctions")
