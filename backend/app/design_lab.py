"""Former account gate for experimental UI.

Rolled out site-wide: keep this module only so older imports/tests do not break.
New UI is enabled for everyone via `design_lab=True` in `_template_context`.
"""

from __future__ import annotations

from typing import Any

# Gate cancelled — retained for reference / migration only.
DESIGN_LAB_EMAILS = frozenset()


def is_design_lab_user(user: Any | None) -> bool:
    """Deprecated. Experimental UI is live for all users."""
    return True
