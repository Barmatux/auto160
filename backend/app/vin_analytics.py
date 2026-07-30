"""Admin report: listings where VIN was obtained."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc, func, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.customs_vin import DATABASE_PERSONAL
from app.listing_enrichment import build_listing_customs_map
from app.models import AvbySyncRunVinCheck, CarListing, VinCustomsCheck


@dataclass(frozen=True)
class VinListingReportRow:
    listing: CarListing
    vin: str | None
    vin_fetched_at: datetime | None
    last_checked_at: datetime | None
    customs_found: bool | None
    customs_release_date: str | None
    customs_checked_at: datetime | None
    sync_checks_count: int


def _sync_checks_table_available(db: Session) -> bool:
    try:
        bind = db.get_bind()
        if bind is None:
            return False
        return inspect(bind).has_table(AvbySyncRunVinCheck.__tablename__)
    except Exception:
        return False


def _latest_sync_checks(db: Session, listing_ids: list[int]) -> dict[int, dict[str, object]]:
    if not listing_ids or not _sync_checks_table_available(db):
        return {}

    try:
        rows = (
            db.query(
                AvbySyncRunVinCheck.listing_id,
                func.count(AvbySyncRunVinCheck.id).label("checks_count"),
                func.max(AvbySyncRunVinCheck.created_at).label("last_checked_at"),
            )
            .filter(
                AvbySyncRunVinCheck.listing_id.in_(listing_ids),
                AvbySyncRunVinCheck.vin_obtained.is_(True),
            )
            .group_by(AvbySyncRunVinCheck.listing_id)
            .all()
        )
    except (OperationalError, ProgrammingError):
        return {}

    return {
        row.listing_id: {
            "checks_count": int(row.checks_count or 0),
            "last_checked_at": row.last_checked_at,
        }
        for row in rows
    }


def _customs_checked_at_map(db: Session, vins: set[str]) -> dict[str, datetime]:
    if not vins:
        return {}

    rows = (
        db.query(VinCustomsCheck)
        .filter(
            VinCustomsCheck.vin.in_(vins),
            VinCustomsCheck.database == DATABASE_PERSONAL,
        )
        .order_by(VinCustomsCheck.checked_at.desc())
        .all()
    )
    result: dict[str, datetime] = {}
    for row in rows:
        if row.vin not in result:
            result[row.vin] = row.checked_at
    return result


def build_vin_listings_report(
    db: Session,
    *,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[VinListingReportRow], int]:
    page = max(page, 1)
    per_page = max(min(per_page, 200), 1)

    query = (
        db.query(CarListing)
        .filter(
            CarListing.vin.isnot(None),
            func.length(CarListing.vin) == 17,
        )
        .order_by(
            desc(func.coalesce(CarListing.vin_fetched_at, CarListing.created_at)),
            desc(CarListing.id),
        )
    )

    total = query.count()
    listings = query.offset((page - 1) * per_page).limit(per_page).all()
    listing_ids = [listing.id for listing in listings]

    customs_map = build_listing_customs_map(db, listings)
    sync_map = _latest_sync_checks(db, listing_ids)

    vins = {(listing.vin or "").strip().upper() for listing in listings}
    vins = {vin for vin in vins if len(vin) == 17}
    customs_checked_at = _customs_checked_at_map(db, vins)

    report: list[VinListingReportRow] = []
    for listing in listings:
        sync_info = sync_map.get(listing.id, {})
        vin = (listing.vin or "").strip().upper()
        customs = customs_map.get(listing.id)
        vin_fetched_at = listing.vin_fetched_at
        last_checked_at = vin_fetched_at or sync_info.get("last_checked_at") or listing.created_at
        if isinstance(last_checked_at, datetime) and last_checked_at.tzinfo is not None:
            last_checked_at = last_checked_at.replace(tzinfo=None)

        customs_checked_at_value = customs_checked_at.get(vin) if vin else None
        report.append(
            VinListingReportRow(
                listing=listing,
                vin=vin,
                vin_fetched_at=vin_fetched_at,
                last_checked_at=last_checked_at,
                customs_found=customs.found if customs else None,
                customs_release_date=customs.release_date if customs else None,
                customs_checked_at=customs_checked_at_value,
                sync_checks_count=int(sync_info.get("checks_count") or 0),
            )
        )

    return report, total
