"""EU (LT/EE) listing policy helpers: ambiguous fields / hybrids → admin CHECK queue."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from sqlalchemy.sql import ColumnElement

    from app.models import CarListing

EU_CHECK_PENDING = "pending"
EU_CHECK_REVIEW = "review"
EU_CHECK_APPROVED = "approved"
EU_CHECK_REJECTED = "rejected"

# pending = missing hp/engine (draft, not in feed); review = hybrid soft-check (may stay published).
EU_CHECK_QUEUE_STATUSES = (EU_CHECK_PENDING, EU_CHECK_REVIEW)

EU_CHECK_SOURCES = ("autoplius", "auto24")

EU_CHECK_REASON_HYBRID = "hybrid"

EU_CHECK_REASON_LABELS = {
    "hp_missing": "нет мощности",
    "engine_l_missing": "нет объёма",
    EU_CHECK_REASON_HYBRID: "гибрид",
}


def format_eu_check_reason(reason: str | None) -> str:
    if not reason:
        return "спорные данные"
    parts = [p.strip() for p in str(reason).split(",") if p.strip()]
    labels = [EU_CHECK_REASON_LABELS.get(p, p) for p in parts]
    return ", ".join(labels) if labels else "спорные данные"


def public_eu_listing_predicate() -> ColumnElement[bool]:
    """Published EU feed: auto-qualified by age/engine, or manually approved."""
    from sqlalchemy import and_, or_

    from app.autoplius_map import DEFAULT_MAX_AGE_YEARS, DEFAULT_MAX_ENGINE_L, min_year_for_max_age
    from app.models import CarListing

    eu_year_min = min_year_for_max_age(DEFAULT_MAX_AGE_YEARS)
    auto_match = and_(
        CarListing.year >= eu_year_min,
        CarListing.engine_capacity_l.isnot(None),
        CarListing.engine_capacity_l <= DEFAULT_MAX_ENGINE_L,
    )
    manual_approved = CarListing.eu_check_status == EU_CHECK_APPROVED
    return or_(auto_match, manual_approved)


def apply_eu_check_on_import(
    listing: Any,
    *,
    check_reason: str | None,
    price_missing: bool,
    engine_type: str | None = None,
) -> None:
    """Set status / eu_check_* after mapped fields and BYN price were applied."""
    from app.fuel_type_labels import is_hybrid_fuel

    previous = (listing.eu_check_status or "").strip() or None
    hybrid = is_hybrid_fuel(engine_type)

    if check_reason:
        if previous == EU_CHECK_REJECTED:
            listing.eu_check_status = EU_CHECK_REJECTED
            listing.eu_check_reason = check_reason
            listing.status = "archived"
            return
        if previous == EU_CHECK_APPROVED:
            listing.eu_check_status = EU_CHECK_APPROVED
            listing.eu_check_reason = check_reason
            listing.status = "draft" if price_missing else "published"
            return
        listing.eu_check_status = EU_CHECK_PENDING
        listing.eu_check_reason = check_reason
        listing.status = "draft"
        return

    # Unambiguous vs hard filters.
    if previous == EU_CHECK_REJECTED and not hybrid:
        listing.eu_check_status = None
        listing.eu_check_reason = None
        listing.status = "draft" if price_missing else "published"
        return

    if previous == EU_CHECK_APPROVED:
        listing.eu_check_status = EU_CHECK_APPROVED
        listing.eu_check_reason = EU_CHECK_REASON_HYBRID if hybrid else None
        listing.status = "draft" if price_missing else "published"
        return

    if previous == EU_CHECK_REJECTED and hybrid:
        # Stay hidden until admin explicitly shows again.
        listing.eu_check_status = EU_CHECK_REJECTED
        listing.eu_check_reason = EU_CHECK_REASON_HYBRID
        listing.status = "archived"
        return

    if hybrid:
        listing.eu_check_status = EU_CHECK_REVIEW
        listing.eu_check_reason = EU_CHECK_REASON_HYBRID
        listing.status = "draft" if price_missing else "published"
        return

    listing.eu_check_status = None
    listing.eu_check_reason = None
    listing.status = "draft" if price_missing else "published"


def archive_eu_listing_on_hard_skip(listing: Any) -> bool:
    """Archive a previously imported EU row that now hard-fails filters. Returns True if changed."""
    changed = False
    if listing.eu_check_status in (*EU_CHECK_QUEUE_STATUSES, EU_CHECK_APPROVED):
        listing.eu_check_status = None
        listing.eu_check_reason = None
        changed = True
    current = getattr(listing.status, "value", listing.status)
    if current != "archived":
        listing.status = "archived"
        changed = True
    return changed


def approve_eu_check_listing(db: Session, listing_id: int) -> CarListing:
    from app.models import CarListing, ListingStatus

    listing = (
        db.query(CarListing)
        .filter(
            CarListing.id == listing_id,
            CarListing.source.in_(EU_CHECK_SOURCES),
        )
        .first()
    )
    if listing is None:
        raise ValueError("Объявление не найдено")
    if listing.eu_check_status == EU_CHECK_REJECTED:
        raise ValueError("Объявление уже скрыто")
    listing.eu_check_status = EU_CHECK_APPROVED
    if listing.price_byn_missing or listing.price is None:
        listing.status = ListingStatus.draft
    else:
        listing.status = ListingStatus.published
    db.commit()
    db.refresh(listing)
    return listing


def reject_eu_check_listing(db: Session, listing_id: int) -> CarListing:
    from app.models import CarListing, ListingStatus

    listing = (
        db.query(CarListing)
        .filter(
            CarListing.id == listing_id,
            CarListing.source.in_(EU_CHECK_SOURCES),
        )
        .first()
    )
    if listing is None:
        raise ValueError("Объявление не найдено")
    listing.eu_check_status = EU_CHECK_REJECTED
    listing.status = ListingStatus.archived
    db.commit()
    db.refresh(listing)
    return listing


def _eu_check_queue_query(db: Session):
    from app.brand_exclusions import exclude_excluded_brands
    from app.full_hybrid_exclusions import listing_is_banned_eu_hybrid
    from app.model_exclusions import exclude_excluded_models
    from app.models import CarListing, ListingStatus

    query = exclude_excluded_brands(
        db.query(CarListing).filter(
            CarListing.source.in_(EU_CHECK_SOURCES),
            CarListing.status != ListingStatus.archived,
            CarListing.eu_check_status.in_(EU_CHECK_QUEUE_STATUSES),
        ),
        CarListing.brand,
    )
    query = exclude_excluded_models(query, CarListing.model, CarListing.title)
    # Full HEV / PHEV are hard-banned — drop leftovers from the CHECK queue.
    banned_ids = [row.id for row in query.all() if listing_is_banned_eu_hybrid(row)]
    if banned_ids:
        query = query.filter(~CarListing.id.in_(banned_ids))
    return query


def count_eu_check_pending(db: Session) -> int:
    return _eu_check_queue_query(db).count()


def paginate_eu_check_pending(
    db: Session,
    *,
    q: str = "",
    page: int = 1,
    per_page: int = 48,
) -> tuple[list[CarListing], int]:
    from sqlalchemy import or_

    from app.models import CarListing

    query = _eu_check_queue_query(db)
    needle = (q or "").strip()
    if needle:
        like = f"%{needle}%"
        query = query.filter(
            or_(
                CarListing.brand.ilike(like),
                CarListing.model.ilike(like),
                CarListing.title.ilike(like),
                CarListing.external_id.ilike(like),
            )
        )
    total = query.count()
    page = max(1, int(page or 1))
    per_page = max(1, int(per_page or 48))
    rows = (
        query.order_by(CarListing.created_at.desc(), CarListing.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return rows, total
