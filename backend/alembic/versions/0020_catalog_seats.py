"""Add catalog_items.has_7_seats for «7 мест» filter."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_catalog_seats"
down_revision: Union[str, None] = "0019_listing_price_byn_missing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("has_7_seats", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_catalog_items_has_7_seats", "catalog_items", ["has_7_seats"], unique=False)
    op.alter_column("catalog_items", "has_7_seats", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_catalog_items_has_7_seats", table_name="catalog_items")
    op.drop_column("catalog_items", "has_7_seats")
