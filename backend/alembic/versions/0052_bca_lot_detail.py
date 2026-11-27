"""BCA lot detail payload from parser card scrape.

Revision ID: 0052_bca_lot_detail
Revises: 0051_bca_lot_photos
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0052_bca_lot_detail"
down_revision: Union[str, None] = "0051_bca_lot_photos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bca_lots", sa.Column("lot_detail", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("bca_lots", "lot_detail")