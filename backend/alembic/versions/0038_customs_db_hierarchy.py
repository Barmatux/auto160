"""Hierarchical customs DB: make → model → liters → exact cc.

Revision ID: 0038_customs_db_hierarchy
Revises: 0037_customs_vehicle_specs
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038_customs_db_hierarchy"
down_revision: Union[str, None] = "0037_customs_vehicle_specs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customs_db_makes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("sort_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_customs_db_makes_name"),
    )
    op.create_index("ix_customs_db_makes_name", "customs_db_makes", ["name"])
    op.create_index("ix_customs_db_makes_sort_weight", "customs_db_makes", ["sort_weight"])
    op.create_index("ix_customs_db_makes_is_active", "customs_db_makes", ["is_active"])

    op.create_table(
        "customs_db_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("make_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sort_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["make_id"], ["customs_db_makes.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("make_id", "name", name="uq_customs_db_models_make_name"),
    )
    op.create_index("ix_customs_db_models_make_id", "customs_db_models", ["make_id"])
    op.create_index("ix_customs_db_models_name", "customs_db_models", ["name"])
    op.create_index("ix_customs_db_models_sort_weight", "customs_db_models", ["sort_weight"])
    op.create_index("ix_customs_db_models_is_active", "customs_db_models", ["is_active"])

    op.create_table(
        "customs_db_engine_liters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_id", sa.Integer(), nullable=False),
        sa.Column("liters", sa.Numeric(4, 1), nullable=False),
        sa.Column("sort_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["customs_db_models.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("model_id", "liters", name="uq_customs_db_engine_liters_model_liters"),
    )
    op.create_index("ix_customs_db_engine_liters_model_id", "customs_db_engine_liters", ["model_id"])
    op.create_index("ix_customs_db_engine_liters_sort_weight", "customs_db_engine_liters", ["sort_weight"])
    op.create_index("ix_customs_db_engine_liters_is_active", "customs_db_engine_liters", ["is_active"])

    op.create_table(
        "customs_db_engine_cc",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("liter_id", sa.Integer(), nullable=False),
        sa.Column("engine_cc", sa.Integer(), nullable=False),
        sa.Column("power_hp", sa.Numeric(8, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["liter_id"], ["customs_db_engine_liters.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("liter_id", "engine_cc", name="uq_customs_db_engine_cc_liter_cc"),
    )
    op.create_index("ix_customs_db_engine_cc_liter_id", "customs_db_engine_cc", ["liter_id"])
    op.create_index("ix_customs_db_engine_cc_sort_weight", "customs_db_engine_cc", ["sort_weight"])
    op.create_index("ix_customs_db_engine_cc_is_active", "customs_db_engine_cc", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_customs_db_engine_cc_is_active", table_name="customs_db_engine_cc")
    op.drop_index("ix_customs_db_engine_cc_sort_weight", table_name="customs_db_engine_cc")
    op.drop_index("ix_customs_db_engine_cc_liter_id", table_name="customs_db_engine_cc")
    op.drop_table("customs_db_engine_cc")
    op.drop_index("ix_customs_db_engine_liters_is_active", table_name="customs_db_engine_liters")
    op.drop_index("ix_customs_db_engine_liters_sort_weight", table_name="customs_db_engine_liters")
    op.drop_index("ix_customs_db_engine_liters_model_id", table_name="customs_db_engine_liters")
    op.drop_table("customs_db_engine_liters")
    op.drop_index("ix_customs_db_models_is_active", table_name="customs_db_models")
    op.drop_index("ix_customs_db_models_sort_weight", table_name="customs_db_models")
    op.drop_index("ix_customs_db_models_name", table_name="customs_db_models")
    op.drop_index("ix_customs_db_models_make_id", table_name="customs_db_models")
    op.drop_table("customs_db_models")
    op.drop_index("ix_customs_db_makes_is_active", table_name="customs_db_makes")
    op.drop_index("ix_customs_db_makes_sort_weight", table_name="customs_db_makes")
    op.drop_index("ix_customs_db_makes_name", table_name="customs_db_makes")
    op.drop_table("customs_db_makes")
