"""add av.by mapping fields to car_listings

Revision ID: 0006_listing_avby_mapping_fields
Revises: 0005_catalog_item_hybrid_specs
Create Date: 2026-06-21 00:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_listing_avby_mapping_fields"
down_revision: Union[str, None] = "0005_catalog_item_hybrid_specs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("car_listings", sa.Column("avby_id", sa.Integer(), nullable=True))
    op.add_column("car_listings", sa.Column("generation", sa.String(length=120), nullable=True))
    op.add_column("car_listings", sa.Column("body_type", sa.String(length=60), nullable=True))
    op.add_column("car_listings", sa.Column("drive_type", sa.String(length=40), nullable=True))
    op.add_column("car_listings", sa.Column("transmission_type", sa.String(length=40), nullable=True))
    op.add_column("car_listings", sa.Column("engine_type", sa.String(length=40), nullable=True))
    op.add_column("car_listings", sa.Column("engine_capacity_l", sa.Numeric(4, 1), nullable=True))
    op.add_column("car_listings", sa.Column("engine_power_hp", sa.Integer(), nullable=True))
    op.add_column("car_listings", sa.Column("vin_indicated", sa.Boolean(), nullable=True))
    op.add_column("car_listings", sa.Column("seller_name", sa.String(length=120), nullable=True))
    op.add_column("car_listings", sa.Column("source_url", sa.String(length=500), nullable=True))
    op.add_column("car_listings", sa.Column("cover_photo_url", sa.String(length=500), nullable=True))
    op.add_column("car_listings", sa.Column("raw_photos", sa.JSON(), nullable=True))

    op.create_index("ix_car_listings_avby_id", "car_listings", ["avby_id"], unique=True, if_not_exists=True)
    op.create_index("ix_car_listings_generation", "car_listings", ["generation"], unique=False, if_not_exists=True)
    op.create_index("ix_car_listings_body_type", "car_listings", ["body_type"], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_car_listings_body_type", table_name="car_listings")
    op.drop_index("ix_car_listings_generation", table_name="car_listings")
    op.drop_index("ix_car_listings_avby_id", table_name="car_listings")

    op.drop_column("car_listings", "raw_photos")
    op.drop_column("car_listings", "cover_photo_url")
    op.drop_column("car_listings", "source_url")
    op.drop_column("car_listings", "seller_name")
    op.drop_column("car_listings", "vin_indicated")
    op.drop_column("car_listings", "engine_power_hp")
    op.drop_column("car_listings", "engine_capacity_l")
    op.drop_column("car_listings", "engine_type")
    op.drop_column("car_listings", "transmission_type")
    op.drop_column("car_listings", "drive_type")
    op.drop_column("car_listings", "body_type")
    op.drop_column("car_listings", "generation")
    op.drop_column("car_listings", "avby_id")
