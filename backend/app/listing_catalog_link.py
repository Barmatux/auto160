"""Match and persist links between car listings and catalog modifications."""

from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import CarListing, CatalogItem, ListingStatus

MIN_LINK_SCORE = 10


def normalize_match_text(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower().replace("ё", "е")


def normalize_model_name(name: str) -> str:
    raw = (name or "").strip().lower().replace("ё", "е")
    raw = re.sub(r"[-_]+", " ", raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw


def canonical_model_name(name: str | None) -> str:
    if not name:
        return ""
    source = (name or "").strip()
    normalized = normalize_model_name(source)
    m = re.match(r"^(\d+)\s*(series|серия)$", normalized)
    if m:
        return f"{m.group(1)} серия"
    m = re.match(r"^(\d+)\s*(series|серия)\s*gran\s*tourer$", normalized)
    if m:
        return f"{m.group(1)} серия Gran Tourer"
    m = re.match(r"^(\d+)\s*(series|серия)\s*active\s*tourer$", normalized)
    if m:
        return f"{m.group(1)} серия Active Tourer"
    m = re.match(r"^x\s*([0-9]+)$", normalized)
    if m:
        return f"X{m.group(1)}"
    m = re.match(r"^i\s*([0-9]+)$", normalized)
    if m:
        return f"i{m.group(1)}"
    return source


def body_types_compatible(catalog_body: str | None, listing_body: str | None) -> bool:
    left = normalize_match_text(catalog_body)
    right = normalize_match_text(listing_body)
    if not left or not right:
        return True
    if left == right:
        return True
    return left in right or right in left


def score_listing_catalog_match(
    listing: CarListing,
    item: CatalogItem,
    *,
    require_cover: bool = False,
) -> int:
    if require_cover and not listing.cover_photo_url:
        return -1
    if normalize_match_text(listing.brand) != normalize_match_text(item.make):
        return -1
    if canonical_model_name(listing.model) != canonical_model_name(item.model):
        return -1
    if not body_types_compatible(item.body_type, listing.body_type):
        return -1

    score = 10
    if item.body_type and listing.body_type:
        if normalize_match_text(item.body_type) == normalize_match_text(listing.body_type):
            score += 40
        else:
            score += 25
    if item.generation and listing.generation:
        if normalize_match_text(item.generation) == normalize_match_text(listing.generation):
            score += 20
        elif normalize_match_text(listing.generation) in normalize_match_text(item.generation):
            score += 10
    if item.year_from is not None and listing.year is not None:
        year_to = item.year_to if item.year_to is not None else item.year_from
        if item.year_from <= listing.year <= year_to:
            score += 15
        elif abs(listing.year - item.year_from) <= 1 or abs(listing.year - year_to) <= 1:
            score += 5
    if item.engine_power_hp is not None and listing.engine_power_hp is not None:
        diff = abs(item.engine_power_hp - listing.engine_power_hp)
        if diff <= 5:
            score += 25
        elif diff <= 15:
            score += 12
        elif diff <= 30:
            score += 5
    return score


def find_best_catalog_item(listing: CarListing, catalog_items: list[CatalogItem]) -> CatalogItem | None:
    best_item: CatalogItem | None = None
    best_score = -1
    for item in catalog_items:
        score = score_listing_catalog_match(listing, item)
        if score < MIN_LINK_SCORE:
            continue
        if score > best_score or (score == best_score and best_item and item.id < best_item.id):
            best_score = score
            best_item = item
    return best_item


def _catalog_candidates(db: Session, listing: CarListing) -> list[CatalogItem]:
    make = (listing.brand or "").strip()
    model = canonical_model_name(listing.model)
    if not make or not model:
        return []
    return (
        db.query(CatalogItem)
        .filter(
            CatalogItem.source_site == "av.by",
            CatalogItem.make.ilike(make),
            CatalogItem.model == model,
            or_(CatalogItem.engine_power_hp.is_(None), CatalogItem.engine_power_hp <= 160),
        )
        .order_by(CatalogItem.year_from.desc(), CatalogItem.id.asc())
        .all()
    )


def link_listing_to_catalog(db: Session, listing: CarListing, *, commit: bool = False) -> CatalogItem | None:
    if listing.catalog_item_id:
        existing = db.get(CatalogItem, listing.catalog_item_id)
        if existing and score_listing_catalog_match(listing, existing) >= MIN_LINK_SCORE:
            return existing

    best = find_best_catalog_item(listing, _catalog_candidates(db, listing))
    listing.catalog_item_id = best.id if best else None
    if commit:
        db.commit()
    return best


def resolve_catalog_items_for_listings(
    db: Session,
    listings: list[CarListing],
) -> dict[int, CatalogItem]:
    if not listings:
        return {}

    item_ids = {listing.catalog_item_id for listing in listings if listing.catalog_item_id}
    items_by_id: dict[int, CatalogItem] = {}
    if item_ids:
        rows = db.query(CatalogItem).filter(CatalogItem.id.in_(item_ids)).all()
        items_by_id = {row.id: row for row in rows}

    result: dict[int, CatalogItem] = {}
    for listing in listings:
        if listing.catalog_item_id and listing.catalog_item_id in items_by_id:
            item = items_by_id[listing.catalog_item_id]
            if score_listing_catalog_match(listing, item) >= MIN_LINK_SCORE:
                result[listing.id] = item
                continue
        matched = find_best_catalog_item(listing, _catalog_candidates(db, listing))
        if matched:
            result[listing.id] = matched
    return result


def fetch_listings_for_catalog_items(
    db: Session,
    items: list[CatalogItem],
    *,
    limit_per_item: int = 200,
) -> dict[int, list[CarListing]]:
    if not items:
        return {}

    item_ids = [item.id for item in items]
    linked_rows = (
        db.query(CarListing)
        .filter(
            CarListing.status == ListingStatus.published,
            CarListing.catalog_item_id.in_(item_ids),
        )
        .order_by(CarListing.created_at.desc())
        .all()
    )
    by_item: dict[int, list[CarListing]] = defaultdict(list)
    for listing in linked_rows:
        if listing.catalog_item_id is None:
            continue
        bucket = by_item[listing.catalog_item_id]
        if len(bucket) < limit_per_item:
            bucket.append(listing)

    missing_items = [item for item in items if not by_item.get(item.id)]
    if not missing_items:
        return dict(by_item)

    pairs = {(item.make or "", canonical_model_name(item.model)) for item in missing_items if item.make and item.model}
    cache: dict[tuple[str, str], list[CarListing]] = {}
    for make, model in pairs:
        if not make or not model:
            continue
        cache[(make, model)] = (
            db.query(CarListing)
            .filter(
                CarListing.status == ListingStatus.published,
                CarListing.catalog_item_id.is_(None),
                CarListing.brand.ilike(make),
                CarListing.model.ilike(model),
            )
            .order_by(CarListing.created_at.desc())
            .limit(limit_per_item)
            .all()
        )

    for item in missing_items:
        listings = cache.get((item.make or "", canonical_model_name(item.model)), [])
        matched = [row for row in listings if score_listing_catalog_match(row, item) >= MIN_LINK_SCORE]
        by_item[item.id] = matched[:limit_per_item]
    return dict(by_item)
