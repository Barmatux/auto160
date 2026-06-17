"""add username to users

Revision ID: 0004_add_username_to_users
Revises: 0003_catalog_item_photos
Create Date: 2026-06-10 18:58:00
"""

import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_add_username_to_users"
down_revision: Union[str, None] = "0003_catalog_item_photos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_username_from_email(email: str) -> str:
    local_part = (email or "").split("@", 1)[0].lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", local_part).strip("_")
    if not normalized:
        normalized = "user"
    return normalized[:60]


def upgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=80), nullable=True))
    bind = op.get_bind()

    users = list(bind.execute(sa.text("SELECT id, email FROM users")).fetchall())
    used: set[str] = set()
    for row in users:
        base = _base_username_from_email(row.email or "")
        candidate = base
        counter = 1
        while candidate in used:
            suffix = f"_{counter}"
            candidate = f"{base[: 80 - len(suffix)]}{suffix}"
            counter += 1
        used.add(candidate)
        bind.execute(sa.text("UPDATE users SET username = :username WHERE id = :id"), {"username": candidate, "id": row.id})

    op.create_index("ix_users_username", "users", ["username"], unique=True)

    if bind.dialect.name == "postgresql":
        op.alter_column("users", "username", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "username")
