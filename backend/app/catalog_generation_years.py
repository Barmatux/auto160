"""Production years for catalog generations (make / model / generation)."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.catalog_ratings import format_production_years, matching_catalog_items
from app.models import CatalogItem

_GENERATION_SLUG_YEARS_RE = re.compile(r"^([a-z0-9]+)-(\d{4})-(\d{4})?$", flags=re.IGNORECASE)
_CATALOG_URL_YEARS_RE = re.compile(r"-(\d{4})-(\d{4})?$")


def parse_years_from_generation_slug(slug: str | None) -> tuple[int | None, int | None]:
    if not slug:
        return None, None
    match = _GENERATION_SLUG_YEARS_RE.match(slug.strip())
    if not match:
        return None, None
    year_from = int(match.group(2))
    year_to = int(match.group(3)) if match.group(3) else None
    return year_from, year_to


def parse_years_from_avby_catalog_url(url: str | None) -> tuple[int | None, int | None]:
    if not url or "av.by/catalog/" not in url:
        return None, None
    if "/catalog/modification/" in url:
        return None, None
    path = url.split("#")[0].split("?")[0].rstrip("/")
    tail = path.rsplit("/", 1)[-1]
    match = _CATALOG_URL_YEARS_RE.search(tail.rstrip("-"))
    if not match:
        return None, None
    year_from = int(match.group(1))
    year_to = int(match.group(2)) if match.group(2) else None
    return year_from, year_to


def years_from_catalog_item(item: CatalogItem) -> tuple[int | None, int | None]:
    raw = item.raw_specs if isinstance(item.raw_specs, dict) else {}
    landing = raw.get("landing") if isinstance(raw.get("landing"), dict) else {}
    generation = landing.get("generation") if isinstance(landing.get("generation"), dict) else {}
    slug = generation.get("slug")
    year_from, year_to = parse_years_from_generation_slug(slug)
    if year_from is not None or year_to is not None:
        return year_from, year_to
    return parse_years_from_avby_catalog_url(item.source_url)


def infer_generation_years(items: list[CatalogItem]) -> tuple[int | None, int | None]:
    found_from: list[int] = []
    found_to: list[int] = []
    for item in items:
        if item.year_from is not None:
            found_from.append(int(item.year_from))
        if item.year_to is not None:
            found_to.append(int(item.year_to))
        inferred_from, inferred_to = years_from_catalog_item(item)
        if inferred_from is not None:
            found_from.append(inferred_from)
        if inferred_to is not None:
            found_to.append(inferred_to)
    year_from = min(found_from) if found_from else None
    year_to = max(found_to) if found_to else None
    return year_from, year_to


def apply_generation_years(
    db: Session,
    *,
    make: str,
    model: str,
    generation: str | None,
    year_from: int | None,
    year_to: int | None,
) -> tuple[list[CatalogItem], int]:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError("Год начала не может быть позже года окончания")
    items = matching_catalog_items(db, make=make, model=model, generation=generation)
    for item in items:
        item.year_from = year_from
        item.year_to = year_to
    return items, len(items)


def sync_generation_years_from_sources(
    db: Session,
    *,
    make: str,
    model: str,
    generation: str | None,
) -> tuple[list[CatalogItem], int, str]:
    items = matching_catalog_items(db, make=make, model=model, generation=generation)
    if not items:
        return [], 0, "—"
    year_from, year_to = infer_generation_years(items)
    if year_from is None and year_to is None:
        return items, 0, "—"
    for item in items:
        item.year_from = year_from
        item.year_to = year_to
    return items, len(items), format_production_years(year_from, year_to)
