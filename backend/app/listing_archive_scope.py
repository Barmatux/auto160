"""Classify av.by listings against catalog make/model/generation scope."""

from __future__ import annotations

import re

from sqlalchemy import and_, exists, func
from sqlalchemy.orm import Session

from app.catalog_ratings import generation_key
from app.catalog_visibility import listing_generation_allowed_for_model
from app.models import CarListing, CatalogItem, ListingStatus

ARCHIVE_REASON_NON_CATALOG = "non_catalog"
ARCHIVE_REASON_WRONG_GENERATION = "wrong_generation"
ARCHIVE_REASON_OTHER = "other"

ARCHIVE_REASON_LABELS: dict[str, str] = {
    ARCHIVE_REASON_NON_CATALOG: "Нет в каталоге",
    ARCHIVE_REASON_WRONG_GENERATION: "Чужое поколение",
    ARCHIVE_REASON_OTHER: "Другое",
}


def normalize_catalog_match_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9]+", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def build_catalog_brand_model_index(db: Session) -> dict[str, set[str]]:
    brand_to_models: dict[str, set[str]] = {}
    rows = (
        db.query(CatalogItem.make, CatalogItem.model)
        .filter(CatalogItem.source_site == "av.by")
        .distinct()
        .all()
    )
    for make, model in rows:
        make_name = (make or "").strip()
        model_name = (model or "").strip()
        if not make_name or not model_name:
            continue
        make_n = normalize_catalog_match_name(make_name)
        model_n = normalize_catalog_match_name(model_name)
        if not make_n or not model_n:
            continue
        brand_to_models.setdefault(make_n, set()).add(model_n)
    return brand_to_models


def build_catalog_generation_index(db: Session) -> dict[tuple[str, str], tuple[frozenset[str], bool]]:
    index: dict[tuple[str, str], tuple[set[str], bool]] = {}
    rows = (
        db.query(CatalogItem)
        .filter(CatalogItem.source_site == "av.by")
        .order_by(CatalogItem.id.asc())
        .all()
    )
    for item in rows:
        make = (item.make or "").strip()
        model = (item.model or "").strip()
        if not make or not model:
            continue
        key = (normalize_catalog_match_name(make), normalize_catalog_match_name(model))
        generations, allows_unrated = index.get(key, (set(), False))
        generation = generation_key(item.generation)
        if generation:
            generations.add(generation)
        else:
            allows_unrated = True
        index[key] = (generations, allows_unrated)
    return {
        key: (frozenset(generations), allows_unrated)
        for key, (generations, allows_unrated) in index.items()
    }


def classify_listing_catalog_scope(
    *,
    brand: str | None,
    model: str | None,
    generation: str | None,
    brand_models: dict[str, set[str]],
    generation_index: dict[tuple[str, str], tuple[frozenset[str], bool]],
) -> str:
    brand_n = normalize_catalog_match_name(brand)
    model_n = normalize_catalog_match_name(model)
    if not brand_n or not model_n:
        return ARCHIVE_REASON_OTHER
    if brand_n not in brand_models or model_n not in brand_models[brand_n]:
        return ARCHIVE_REASON_NON_CATALOG
    catalog_generations, catalog_allows_unrated = generation_index.get(
        (brand_n, model_n),
        (frozenset(), False),
    )
    if listing_generation_allowed_for_model(
        generation,
        catalog_generations=catalog_generations,
        catalog_allows_unrated=catalog_allows_unrated,
    ):
        return ARCHIVE_REASON_OTHER
    return ARCHIVE_REASON_WRONG_GENERATION


def catalog_make_model_exists():
    return exists().where(
        and_(
            CatalogItem.source_site == "av.by",
            func.lower(CatalogItem.make) == func.lower(CarListing.brand),
            func.lower(CatalogItem.model) == func.lower(CarListing.model),
        )
    )


def archived_avby_listings_query(db: Session):
    return db.query(CarListing).filter(
        CarListing.avby_id.isnot(None),
        CarListing.status == ListingStatus.archived,
    )


def count_archived_by_scope(
    db: Session,
    *,
    brand_models: dict[str, set[str]],
    generation_index: dict[tuple[str, str], tuple[frozenset[str], bool]],
) -> dict[str, int]:
    counts = {
        ARCHIVE_REASON_NON_CATALOG: 0,
        ARCHIVE_REASON_WRONG_GENERATION: 0,
        ARCHIVE_REASON_OTHER: 0,
    }
    rows = (
        archived_avby_listings_query(db)
        .with_entities(CarListing.brand, CarListing.model, CarListing.generation)
        .all()
    )
    for brand, model, generation in rows:
        reason = classify_listing_catalog_scope(
            brand=brand,
            model=model,
            generation=generation,
            brand_models=brand_models,
            generation_index=generation_index,
        )
        counts[reason] += 1
    return counts


def paginate_archived_listings(
    db: Session,
    *,
    reason: str,
    q: str,
    page: int,
    per_page: int,
    brand_models: dict[str, set[str]],
    generation_index: dict[tuple[str, str], tuple[frozenset[str], bool]],
) -> tuple[list[CarListing], int, dict[int, str]]:
    if reason == ARCHIVE_REASON_NON_CATALOG:
        query = archived_avby_listings_query(db).filter(~catalog_make_model_exists())
        if q.strip():
            pattern = f"%{q.strip()}%"
            query = query.filter(
                CarListing.brand.ilike(pattern) | CarListing.model.ilike(pattern)
            )
        total = query.count()
        offset = (page - 1) * per_page
        rows = (
            query.order_by(CarListing.created_at.desc(), CarListing.id.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )
        reasons = {row.id: ARCHIVE_REASON_NON_CATALOG for row in rows}
        return rows, total, reasons

    candidates = archived_avby_listings_query(db)
    if q.strip():
        pattern = f"%{q.strip()}%"
        candidates = candidates.filter(
            CarListing.brand.ilike(pattern) | CarListing.model.ilike(pattern)
        )
    candidate_rows = (
        candidates.with_entities(
            CarListing.id,
            CarListing.brand,
            CarListing.model,
            CarListing.generation,
            CarListing.created_at,
        )
        .order_by(CarListing.created_at.desc(), CarListing.id.desc())
        .all()
    )
    matched_ids: list[int] = []
    reasons: dict[int, str] = {}
    for listing_id, brand, model, generation, _created_at in candidate_rows:
        scope_reason = classify_listing_catalog_scope(
            brand=brand,
            model=model,
            generation=generation,
            brand_models=brand_models,
            generation_index=generation_index,
        )
        if reason != "all" and scope_reason != reason:
            continue
        matched_ids.append(listing_id)
        reasons[listing_id] = scope_reason

    total = len(matched_ids)
    offset = (page - 1) * per_page
    page_ids = matched_ids[offset : offset + per_page]
    if not page_ids:
        return [], total, reasons

    rows = db.query(CarListing).filter(CarListing.id.in_(page_ids)).all()
    rows_by_id = {row.id: row for row in rows}
    ordered_rows = [rows_by_id[listing_id] for listing_id in page_ids if listing_id in rows_by_id]
    return ordered_rows, total, reasons
