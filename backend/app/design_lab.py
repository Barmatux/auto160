"""Account-gated design preview. Only listed emails see experimental UI."""

from __future__ import annotations

from typing import Any

# Design changes apply only for these accounts until the gate is cancelled.
DESIGN_LAB_EMAILS = frozenset(
    {
        "cargo.shleg@gmail.com",
    }
)


def is_design_lab_user(user: Any | None) -> bool:
    if user is None:
        return False
    email = (getattr(user, "email", None) or "").strip().lower()
    return email in DESIGN_LAB_EMAILS
