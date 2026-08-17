"""Admin report: listings where VIN was obtained."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time
from urllib.parse import urlencode

from sqlalchemy import desc, func, inspect, or_
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.customs_vin import DATABASE_PERSONAL
from app.listing_enrichment import build_listing_customs_map
from app.models import AvbySyncRunVinCheck, CarListing, VinCustomsCheck

CUSTOMS_FILTER_OPTIONS = (
    ("", "Все"),
    ("found", "Найдено"),
    ("not_found", "Не найдено"),
    ("unchecked", "Не проверялось"),
)


@dataclass(frozen=True)
class VinListingFilters:
    auto: str = ""
    vin: str = ""
    customs: str = ""
    import_from: str = ""
    import_to: str = ""
    vin_from: str = ""
    vin_to: str = ""
    customs_from: str = ""
    customs_to: str = ""

    def active(self) -> bool:
        return any(
            (
                self.auto,
                self.vin,
                self.customs,
                self.import_from,
                self.import_to,
                self.vin_from,
                self.vin_to,
                self.customs_from,
                self.customs_to,
            )
        )

    def query_pairs(self, *, page: int | None = None) -> list[tuple[str, str]]:
        pairs = [("tab", "vin")]
        for key in (
            "auto",
            "vin",
            "customs",
            "import_from",
            "import_to",
            "vin_from",
            "vin_to",
            "customs_from",
            "customs_to",
        ):
            value = getattr(self, key)
            if value:
                pairs.append((key, value))
        if page and page > 1:
            pairs.append(("page", str(page)))
        return pairs

    def query_string(self, *, page: int | None = None) -> str:
        return urlencode(self.query_pairs(page=page))


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


def parse_filter_date(raw: str | None) -> date | None:
    cleaned = (raw or "").strip()
    if not cleaned:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned[:10], fmt).date()
        except ValueError:
            continue
    match = re.search(r"(\d{2})[./](\d{2})[./](\d{4})", cleaned)
    if not match:
        return None
    try:
        return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
    except ValueError:
        return None


def import_date_in_range(release_date: str | None, start: date | None, end: date | None) -> bool:
    if start is None and end is None:
        return True
    parsed = parse_filter_date(release_date)
    if parsed is None:
        return False
    if start and parsed < start:
        return False
    if end and parsed > end:
        return False
    return True


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


def _latest_customs_subquery(db: Session):
    return (
        db.query(
            VinCustomsCheck.vin.label("vin"),
            func.max(VinCustomsCheck.id).label("max_id"),
        )
        .filter(VinCustomsCheck.database == DATABASE_PERSONAL)
        .group_by(VinCustomsCheck.vin)
        .subquery()
    )


def build_vin_listings_report(
    db: Session,
    *,
    page: int = 1,
    per_page: int = 50,
    filters: VinListingFilters | None = None,
) -> tuple[list[VinListingReportRow], int]:
    page = max(page, 1)
    per_page = max(min(per_page, 200), 1)
    filters = filters or VinListingFilters()

    latest_customs = _latest_customs_subquery(db)
    query = (
        db.query(CarListing, VinCustomsCheck)
        .outerjoin(latest_customs, func.upper(CarListing.vin) == latest_customs.c.vin)
        .outerjoin(VinCustomsCheck, VinCustomsCheck.id == latest_customs.c.max_id)
        .filter(
            CarListing.vin.isnot(None),
            func.length(CarListing.vin) == 17,
        )
        .order_by(
            desc(func.coalesce(CarListing.vin_fetched_at, CarListing.created_at)),
            desc(CarListing.id),
        )
    )

    auto = filters.auto.strip()
    if auto:
        like = f"%{auto}%"
        id_match = None
        if auto.isdigit():
            id_match = CarListing.id == int(auto)
        year_match = None
        if len(auto) == 4 and auto.isdigit():
            year_match = CarListing.year == int(auto)
        conditions = [
            CarListing.brand.ilike(like),
            CarListing.model.ilike(like),
            CarListing.city.ilike(like),
        ]
        if id_match is not None:
            conditions.append(id_match)
        if year_match is not None:
            conditions.append(year_match)
        query = query.filter(or_(*conditions))

    vin_query = filters.vin.strip()
    if vin_query:
        query = query.filter(CarListing.vin.ilike(f"%{vin_query}%"))

    vin_from = parse_filter_date(filters.vin_from)
    vin_to = parse_filter_date(filters.vin_to)
    if vin_from:
        query = query.filter(CarListing.vin_fetched_at >= datetime.combine(vin_from, time.min))
    if vin_to:
        query = query.filter(CarListing.vin_fetched_at <= datetime.combine(vin_to, time.max))

    customs_from = parse_filter_date(filters.customs_from)
    customs_to = parse_filter_date(filters.customs_to)
    if customs_from:
        query = query.filter(VinCustomsCheck.checked_at >= datetime.combine(customs_from, time.min))
    if customs_to:
        query = query.filter(VinCustomsCheck.checked_at <= datetime.combine(customs_to, time.max))

    if filters.customs == "found":
        query = query.filter(VinCustomsCheck.found.is_(True))
    elif filters.customs == "not_found":
        query = query.filter(VinCustomsCheck.found.is_(False))
    elif filters.customs == "unchecked":
        query = query.filter(VinCustomsCheck.id.is_(None))

    import_from = parse_filter_date(filters.import_from)
    import_to = parse_filter_date(filters.import_to)
    if import_from or import_to:
        query = query.filter(
            VinCustomsCheck.release_date.isnot(None),
            VinCustomsCheck.release_date != "",
        )

    matched = query.all()
    if import_from or import_to:
        matched = [
            (listing, customs)
            for listing, customs in matched
            if import_date_in_range(customs.release_date if customs else None, import_from, import_to)
        ]

    total = len(matched)
    offset = (page - 1) * per_page
    page_rows = matched[offset : offset + per_page]
    listings = [listing for listing, _customs in page_rows]
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
