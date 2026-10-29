"""Brands we never show or import (out of Auto160 scope)."""

from __future__ import annotations

from sqlalchemy import and_, or_

# Lowercased brand keys / prefixes.
EXCLUDED_BRAND_KEYS = frozenset(
    {
        "aixam",
        "chatenet",
    }
)


def normalize_brand_key(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().lower().replace("ё", "е").split())


def is_excluded_brand(value: str | None) -> bool:
    key = normalize_brand_key(value)
    if not key:
        return False
    if key in EXCLUDED_BRAND_KEYS:
        return True
    return any(key.startswith(f"{blocked} ") or key.startswith(f"{blocked}-") for blocked in EXCLUDED_BRAND_KEYS)


def exclude_excluded_brands(query, column):
    """Drop excluded brands from listing/catalog brand queries."""
    predicates = []
    for blocked in EXCLUDED_BRAND_KEYS:
        predicates.append(~column.ilike(blocked))
        predicates.append(~column.ilike(f"{blocked} %"))
        predicates.append(~column.ilike(f"{blocked}-%"))
    return query.filter(or_(column.is_(None), and_(*predicates)))
