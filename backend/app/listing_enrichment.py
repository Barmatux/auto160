"""Auto-fetch VIN and customs data for listings tied to catalog rating=1."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.avby_vin import AvbyVinError, get_or_fetch_listing_vin
from app.customs_vin import DATABASE_PERSONAL, CustomsVinError, has_fresh_customs_check, lookup_customs_vin
from app.models import CarListing, CatalogItem, VinCustomsCheck


def normalize_catalog_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9]+", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


@dataclass(frozen=True)
class RatingOneTarget:
    make_n: str
    model_n: str
    year_from: int | None
    year_to: int | None


@dataclass
class ListingEnrichmentStats:
    eligible: int = 0
    attempted: int = 0
    vin_fetched: int = 0
    vin_cached: int = 0
    customs_checked: int = 0
    customs_cached: int = 0
    skipped_already_enriched: int = 0
    skipped_limit: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ListingCustomsSummary:
    found: bool
    release_date: str | None
    checked_at: object | None
    cached: bool = False


def build_rating_one_targets(db: Session) -> list[RatingOneTarget]:
    rows = (
        db.query(CatalogItem)
        .filter(
            CatalogItem.rating == 1,
            CatalogItem.source_site == "av.by",
        )
        .all()
    )
    targets: list[RatingOneTarget] = []
    seen: set[tuple[str, str, int | None, int | None]] = set()
    for item in rows:
        make_n = normalize_catalog_name(item.make)
        model_n = normalize_catalog_name(item.model)
        if not make_n or not model_n:
            continue
        key = (make_n, model_n, item.year_from, item.year_to)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            RatingOneTarget(
                make_n=make_n,
                model_n=model_n,
                year_from=item.year_from,
                year_to=item.year_to,
            )
        )
    return targets


def listing_matches_rating_one(listing: CarListing, targets: list[RatingOneTarget]) -> bool:
    if not targets or not listing.brand or not listing.model:
        return False
    make_n = normalize_catalog_name(listing.brand)
    model_n = normalize_catalog_name(listing.model)
    year = listing.year
    for target in targets:
        if target.make_n != make_n or target.model_n != model_n:
            continue
        if target.year_from is not None and year < target.year_from:
            continue
        if target.year_to is not None and year > target.year_to:
            continue
        return True
    return False


def listing_has_saved_vin(listing: CarListing) -> bool:
    return len((listing.vin or "").strip()) == 17


def listing_needs_enrichment(db: Session, listing: CarListing) -> bool:
    if not listing_has_saved_vin(listing):
        return True
    return not has_fresh_customs_check(db, listing.vin or "", database=DATABASE_PERSONAL)


def enrich_listing_vin_and_customs(db: Session, listing: CarListing) -> ListingEnrichmentStats:
    stats = ListingEnrichmentStats(attempted=1)
    if not listing.avby_id:
        stats.errors.append(f"listing {listing.id}: no av.by id")
        return stats

    vin = (listing.vin or "").strip().upper()
    if listing_has_saved_vin(listing):
        stats.vin_cached += 1
    else:
        try:
            vin_result = get_or_fetch_listing_vin(db, listing)
        except AvbyVinError as exc:
            stats.errors.append(f"listing {listing.id}: {exc}")
            return stats

        vin = (vin_result.vin or "").strip().upper()
        if not vin:
            stats.errors.append(f"listing {listing.id}: empty VIN")
            return stats

        if vin_result.cached:
            stats.vin_cached += 1
        else:
            stats.vin_fetched += 1

    if has_fresh_customs_check(db, vin, database=DATABASE_PERSONAL):
        stats.customs_cached += 1
        return stats

    try:
        customs_result = lookup_customs_vin(db, vin, database=DATABASE_PERSONAL)
    except CustomsVinError as exc:
        stats.errors.append(f"listing {listing.id}: customs {exc}")
        return stats

    stats.customs_checked += 1
    if customs_result.cached:
        stats.customs_cached += 1
    return stats


def enrich_rating_one_listings(
    db: Session,
    listings: list[CarListing],
    *,
    targets: list[RatingOneTarget] | None = None,
    limit: int | None = 20,
) -> ListingEnrichmentStats:
    if not listings:
        return ListingEnrichmentStats()

    rating_targets = targets if targets is not None else build_rating_one_targets(db)
    total = ListingEnrichmentStats()
    processed = 0

    for listing in listings:
        if not listing_matches_rating_one(listing, rating_targets):
            continue
        total.eligible += 1

        if not listing_needs_enrichment(db, listing):
            total.skipped_already_enriched += 1
            continue

        if limit is not None and processed >= limit:
            total.skipped_limit += 1
            continue

        item_stats = enrich_listing_vin_and_customs(db, listing)
        total.attempted += item_stats.attempted
        total.vin_fetched += item_stats.vin_fetched
        total.vin_cached += item_stats.vin_cached
        total.customs_checked += item_stats.customs_checked
        total.customs_cached += item_stats.customs_cached
        total.errors.extend(item_stats.errors)
        processed += 1

        if any("429" in err or "Daily VIN limit" in err for err in item_stats.errors):
            break

    return total


def get_listing_customs_summary(db: Session, listing: CarListing) -> ListingCustomsSummary | None:
    vin = (listing.vin or "").strip().upper()
    if len(vin) != 17:
        return None
    row = (
        db.query(VinCustomsCheck)
        .filter(
            VinCustomsCheck.vin == vin,
            VinCustomsCheck.database == DATABASE_PERSONAL,
        )
        .order_by(VinCustomsCheck.checked_at.desc())
        .first()
    )
    if row is None:
        return None
    return ListingCustomsSummary(
        found=row.found,
        release_date=row.release_date,
        checked_at=row.checked_at,
        cached=True,
    )


def build_listing_customs_map(db: Session, listings: list[CarListing]) -> dict[int, ListingCustomsSummary]:
    vins = {(listing.id, (listing.vin or "").strip().upper()) for listing in listings}
    vin_values = {vin for _, vin in vins if len(vin) == 17}
    if not vin_values:
        return {}

    rows = (
        db.query(VinCustomsCheck)
        .filter(
            VinCustomsCheck.vin.in_(vin_values),
            VinCustomsCheck.database == DATABASE_PERSONAL,
        )
        .order_by(VinCustomsCheck.checked_at.desc())
        .all()
    )
    by_vin: dict[str, VinCustomsCheck] = {}
    for row in rows:
        if row.vin not in by_vin:
            by_vin[row.vin] = row

    result: dict[int, ListingCustomsSummary] = {}
    for listing_id, vin in vins:
        row = by_vin.get(vin)
        if row is None:
            continue
        result[listing_id] = ListingCustomsSummary(
            found=row.found,
            release_date=row.release_date,
            checked_at=row.checked_at,
            cached=True,
        )
    return result
