"""Add catalog_items.engine_capacity_cc and backfill from raw_specs.

Revision ID: 0040_catalog_engine_capacity_cc
Revises: 0039_catalog_customs_calc
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_catalog_engine_capacity_cc"
down_revision: Union[str, None] = "0039_catalog_customs_calc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "catalog_items",
        sa.Column("engine_capacity_cc", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_catalog_items_engine_capacity_cc",
        "catalog_items",
        ["engine_capacity_cc"],
    )
    # Prefer digits from modification_detail.engineCapacity ("999 см.куб."),
    # else round(engine_volume_l * 1000).
    op.execute(
        """
        UPDATE catalog_items AS ci
        SET engine_capacity_cc = sub.cc
        FROM (
            SELECT
                id,
                CASE
                    WHEN digits <> ''
                         AND digits ~ '^[0-9]+$'
                         AND digits::integer BETWEEN 1 AND 20000
                    THEN digits::integer
                    WHEN engine_volume_l IS NOT NULL AND engine_volume_l > 0
                    THEN ROUND(engine_volume_l::numeric * 1000)::integer
                    ELSE NULL
                END AS cc
            FROM (
                SELECT
                    id,
                    engine_volume_l,
                    regexp_replace(
                        COALESCE(raw_specs #>> '{modification_detail,engineCapacity}', ''),
                        '[^0-9]',
                        '',
                        'g'
                    ) AS digits
                FROM catalog_items
            ) parsed
        ) AS sub
        WHERE ci.id = sub.id
          AND sub.cc IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_items_engine_capacity_cc", table_name="catalog_items")
    op.drop_column("catalog_items", "engine_capacity_cc")
