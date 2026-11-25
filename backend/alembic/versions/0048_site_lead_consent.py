"""Record personal-data consent on public leads.

Revision ID: 0048_site_lead_consent
Revises: 0047_sold_cars
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048_site_lead_consent"
down_revision: Union[str, None] = "0047_sold_cars"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("site_leads", sa.Column("consent_at", sa.DateTime(), nullable=True))
    op.add_column("site_leads", sa.Column("consent_version", sa.String(20), nullable=True))
    op.add_column(
        "site_leads",
        sa.Column("consent_marketing", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("site_leads", "consent_marketing")
    op.drop_column("site_leads", "consent_version")
    op.drop_column("site_leads", "consent_at")
