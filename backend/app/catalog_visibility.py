"""Hide catalog generations from public catalog views."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog_ratings import matching_catalog_items
from app.models import CatalogItem


def apply_visible_catalog_filter(query):
    return query.filter(CatalogItem.hidden_from_catalog.is_(False))


def apply_generation_catalog_visibility(
    db: Session,
    *,
    make: str,
    model: str,
    generation: str | None,
    hidden: bool,
) -> tuple[list[CatalogItem], int]:
    items = matching_catalog_items(db, make=make, model=model, generation=generation)
    for item in items:
        item.hidden_from_catalog = hidden
    return items, len(items)
