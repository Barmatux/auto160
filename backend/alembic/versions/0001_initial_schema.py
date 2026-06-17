"""initial schema

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-06-09 15:05:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role_enum = postgresql.ENUM("guest", "seller", "admin", name="userrole", create_type=False)
listing_status_enum = postgresql.ENUM("draft", "published", "archived", name="listingstatus", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                CREATE TYPE userrole AS ENUM ('guest', 'seller', 'admin');
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END$$;
            """
        )
        op.execute(
            """
            DO $$
            BEGIN
                CREATE TYPE listingstatus AS ENUM ('draft', 'published', 'archived');
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END$$;
            """
        )
    else:
        user_role_enum.create(bind, checkfirst=True)
        listing_status_enum.create(bind, checkfirst=True)

    if not inspector.has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", user_role_enum, nullable=False, server_default="seller"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    op.create_index("ix_users_id", "users", ["id"], unique=False, if_not_exists=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True, if_not_exists=True)

    if not inspector.has_table("car_listings"):
        op.create_table(
            "car_listings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("seller_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("brand", sa.String(length=80), nullable=False),
            sa.Column("model", sa.String(length=80), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("mileage", sa.Integer(), nullable=False),
            sa.Column("price", sa.Numeric(12, 2), nullable=False),
            sa.Column("city", sa.String(length=80), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", listing_status_enum, nullable=False, server_default="draft"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    op.create_index("ix_car_listings_id", "car_listings", ["id"], unique=False, if_not_exists=True)
    op.create_index("ix_car_listings_seller_id", "car_listings", ["seller_id"], unique=False, if_not_exists=True)
    op.create_index("ix_car_listings_brand", "car_listings", ["brand"], unique=False, if_not_exists=True)
    op.create_index("ix_car_listings_model", "car_listings", ["model"], unique=False, if_not_exists=True)
    op.create_index("ix_car_listings_year", "car_listings", ["year"], unique=False, if_not_exists=True)
    op.create_index("ix_car_listings_price", "car_listings", ["price"], unique=False, if_not_exists=True)
    op.create_index("ix_car_listings_city", "car_listings", ["city"], unique=False, if_not_exists=True)
    op.create_index("ix_car_listings_status", "car_listings", ["status"], unique=False, if_not_exists=True)
    op.create_index("ix_car_listings_created_at", "car_listings", ["created_at"], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_car_listings_created_at", table_name="car_listings")
    op.drop_index("ix_car_listings_status", table_name="car_listings")
    op.drop_index("ix_car_listings_city", table_name="car_listings")
    op.drop_index("ix_car_listings_price", table_name="car_listings")
    op.drop_index("ix_car_listings_year", table_name="car_listings")
    op.drop_index("ix_car_listings_model", table_name="car_listings")
    op.drop_index("ix_car_listings_brand", table_name="car_listings")
    op.drop_index("ix_car_listings_seller_id", table_name="car_listings")
    op.drop_index("ix_car_listings_id", table_name="car_listings")
    op.drop_table("car_listings")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS listingstatus")
        op.execute("DROP TYPE IF EXISTS userrole")
    else:
        listing_status_enum.drop(bind, checkfirst=True)
        user_role_enum.drop(bind, checkfirst=True)
