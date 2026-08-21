"""Import/listing admin helpers for av.by adverts without BYN price."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import CarListing, ListingStatus


def listings_missing_byn_price_query(db: Session):
    return (
        db.query(CarListing)
        .filter(
            CarListing.avby_id.isnot(None),
            CarListing.price_byn_missing.is_(True),
        )
        .order_by(CarListing.created_at.desc(), CarListing.id.desc())
    )


def count_listings_missing_byn_price(db: Session) -> int:
    return listings_missing_byn_price_query(db).count()


def paginate_listings_missing_byn_price(
    db: Session,
    *,
    q: str,
    page: int,
    per_page: int,
) -> tuple[list[CarListing], int]:
    query = listings_missing_byn_price_query(db)
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(CarListing.brand.ilike(pattern) | CarListing.model.ilike(pattern))
    total = query.count()
    offset = (page - 1) * per_page
    rows = query.offset(offset).limit(per_page).all()
    return rows, total


def apply_import_byn_price_state(
    listing: CarListing,
    *,
    price_byn: float | None,
    price_byn_missing: bool,
) -> None:
    """Update listing price fields and publication status after av.by import."""
    was_waiting_for_byn = listing.price_byn_missing
    listing.price_byn_missing = price_byn_missing
    if price_byn_missing:
        listing.price = None
        listing.status = ListingStatus.draft
        return
    listing.price = price_byn
    if was_waiting_for_byn and listing.status == ListingStatus.draft:
        listing.status = ListingStatus.published
