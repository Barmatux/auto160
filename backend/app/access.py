"""Role helpers for limited staff tools (contracts + AV Search)."""

from __future__ import annotations

from app.models import User, UserRole


def is_admin_user(user: User | None) -> bool:
    return user is not None and user.role == UserRole.admin


def can_access_contracts(user: User | None) -> bool:
    return user is not None and user.role in {UserRole.admin, UserRole.staff}


def can_access_av_search(user: User | None) -> bool:
    return user is not None and user.role in {UserRole.admin, UserRole.staff}
