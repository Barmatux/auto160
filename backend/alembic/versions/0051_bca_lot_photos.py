"""Store the BCA lot photo gallery.

Revision ID: 0051_bca_lot_photos
Revises: 0050_lead_funnel_telegram
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051_bca_lot_photos"
down_revision: Union[str, None] = "0050_lead_funnel_telegram"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bca_lots", sa.Column("photo_urls", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("bca_lots", "photo_urls")
