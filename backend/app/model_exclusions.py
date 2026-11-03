"""Models we never show or import (sanctions / out of Auto160 scope)."""

from __future__ import annotations

from sqlalchemy import and_, or_

# Substrings matched against normalized model/title (lowercase).
# "prius" covers Prius, Prius+, Prius C, Prius V, Prius Prime, Prius PHV, etc.
EXCLUDED_MODEL_MARKERS = frozenset(
    {
        "prius",
    }
)


def normalize_model_key(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().replace("ё", "е").split())


def is_excluded_model(
    model: str | None = None,
    *,
    title: str | None = None,
) -> bool:
    """True if model or title is a banned Prius (or other excluded) variant."""
    for raw in (model, title):
        key = normalize_model_key(raw)
        if not key:
            continue
        for marker in EXCLUDED_MODEL_MARKERS:
            if marker in key:
                return True
    return False


def exclude_excluded_models(query, model_column, title_column=None):
    """Drop excluded models from listing queries (model and optional title)."""
    predicates = []
    for marker in EXCLUDED_MODEL_MARKERS:
        like = f"%{marker}%"
        hit = [model_column.ilike(like)]
        if title_column is not None:
            hit.append(title_column.ilike(like))
        predicates.append(~or_(*hit))
    return query.filter(and_(*predicates))
