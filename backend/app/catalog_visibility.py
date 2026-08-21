"""Hide catalog generations from public catalog views."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.catalog_ratings import UNRATED_GENERATION_LABEL, generation_key, matching_catalog_items
from app.models import CarListing, CatalogItem, ListingStatus


@dataclass(frozen=True)
class GenerationVisibilityResult:
    items: list[CatalogItem]
    updated_items: int
    archived_listings: int


def apply_visible_catalog_filter(query):
    return query.filter(CatalogItem.hidden_from_catalog.is_(False))


def listing_matches_generation(listing_generation: str | None, target_generation: str | None) -> bool:
    from app.listing_catalog_link import normalize_match_text

    target_key = generation_key(target_generation)
    normalized_listing = normalize_match_text(listing_generation)
    if not target_key or target_key == UNRATED_GENERATION_LABEL:
        return not normalized_listing
    target = normalize_match_text(target_key)
    if not normalized_listing or not target:
        return False
    if normalized_listing == target:
        return True
    if normalized_listing.endswith(f"({target})"):
        return True
    if normalized_listing.startswith(f"{target} ") or normalized_listing.startswith(f"{target}·"):
        return True
    return False


def listing_generation_allowed_for_model(
    listing_generation: str | None,
    *,
    catalog_generations: frozenset[str] | set[str],
    catalog_allows_unrated: bool,
) -> bool:
    """True when advert generation matches at least one catalog generation for the model."""
    if catalog_generations:
        return any(
            listing_matches_generation(listing_generation, catalog_generation)
            for catalog_generation in catalog_generations
        )
    if catalog_allows_unrated:
        return listing_matches_generation(listing_generation, "")
    return False


def find_listings_for_catalog_generation(
    db: Session,
    *,
    make: str,
    model: str,
    generation: str | None,
    catalog_item_ids: list[int] | None = None,
) -> list[CarListing]:
    from app.listing_catalog_link import canonical_model_name

    make_name = (make or "").strip()
    model_canonical = canonical_model_name(model)
    if not make_name or not model_canonical:
        return []

    matched: dict[int, CarListing] = {}
    item_ids = [item_id for item_id in (catalog_item_ids or []) if item_id]
    if item_ids:
        for listing in db.query(CarListing).filter(CarListing.catalog_item_id.in_(item_ids)).all():
            matched[listing.id] = listing

    rows = (
        db.query(CarListing)
        .filter(func.lower(CarListing.brand) == make_name.lower())
        .order_by(CarListing.id.asc())
        .all()
    )
    for listing in rows:
        if canonical_model_name(listing.model).lower() != model_canonical.lower():
            continue
        if listing_matches_generation(listing.generation, generation):
            matched[listing.id] = listing
    return list(matched.values())


def apply_generation_catalog_visibility(
    db: Session,
    *,
    make: str,
    model: str,
    generation: str | None,
    hidden: bool,
) -> GenerationVisibilityResult:
    items = matching_catalog_items(db, make=make, model=model, generation=generation)
    for item in items:
        item.hidden_from_catalog = hidden

    archived_listings = 0
    if hidden and items:
        listings = find_listings_for_catalog_generation(
            db,
            make=make,
            model=model,
            generation=generation,
            catalog_item_ids=[item.id for item in items],
        )
        for listing in listings:
            if listing.status == ListingStatus.published:
                listing.status = ListingStatus.archived
                archived_listings += 1

    return GenerationVisibilityResult(
        items=items,
        updated_items=len(items),
        archived_listings=archived_listings,
    )
