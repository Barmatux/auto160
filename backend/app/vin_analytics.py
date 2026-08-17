"""Admin report: listings where VIN was obtained."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from urllib.parse import urlencode

from sqlalchemy import func, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.customs_vin import DATABASE_PERSONAL
from app.listing_enrichment import build_listing_customs_map
from app.models import AvbySyncRunVinCheck, CarListing, VinCustomsCheck

SORT_COLUMNS = ("auto", "vin", "customs", "import", "dates")
DEFAULT_SORT = "dates"
DEFAULT_DIR = "desc"
DESC_DEFAULT_COLUMNS = {"customs", "import", "dates"}


@dataclass(frozen=True)
class VinListingSort:
    sort: str = DEFAULT_SORT
    direction: str = DEFAULT_DIR

    def normalized(self) -> "VinListingSort":
        sort = self.sort if self.sort in SORT_COLUMNS else DEFAULT_SORT
        direction = "asc" if self.direction == "asc" else "desc"
        return VinListingSort(sort=sort, direction=direction)

    def query_pairs(self, *, page: int | None = None) -> list[tuple[str, str]]:
        current = self.normalized()
        pairs = [("tab", "vin")]
        if current.sort != DEFAULT_SORT:
            pairs.append(("sort", current.sort))
        if current.direction != DEFAULT_DIR or current.sort != DEFAULT_SORT:
            pairs.append(("dir", current.direction))
        if page and page > 1:
            pairs.append(("page", str(page)))
        return pairs

    def query_string(self, *, page: int | None = None) -> str:
        return urlencode(self.query_pairs(page=page))

    def toggle_url(self, column: str, *, page: int | None = None) -> str:
        current = self.normalized()
        if column == current.sort:
            next_dir = "asc" if current.direction == "desc" else "desc"
        else:
            next_dir = "desc" if column in DESC_DEFAULT_COLUMNS else "asc"
        return VinListingSort(sort=column, direction=next_dir).query_string(page=page)

    def arrow(self, column: str) -> str:
        current = self.normalized()
        if column != current.sort:
            return "↕"
        return "↓" if current.direction == "desc" else "↑"


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


def _sort_key(listing: CarListing, customs: VinCustomsCheck | None, sort: str):
    listing_id = listing.id or 0
    if sort == "auto":
        return (
            (listing.brand or "").casefold(),
            (listing.model or "").casefold(),
            listing.year or 0,
            listing_id,
        )
    if sort == "vin":
        return ((listing.vin or "").upper(), listing_id)
    if sort == "customs":
        if customs is None:
            status = 0
        elif customs.found:
            status = 2
        else:
            status = 1
        return (status, listing_id)
    if sort == "import":
        parsed = parse_filter_date(customs.release_date if customs else None)
        return (parsed is not None, parsed or date.min, listing_id)
    fetched = listing.vin_fetched_at or listing.created_at
    return (fetched is not None, fetched or datetime.min, listing_id)


def build_vin_listings_report(
    db: Session,
    *,
    page: int = 1,
    per_page: int = 50,
    sort: VinListingSort | None = None,
) -> tuple[list[VinListingReportRow], int]:
    page = max(page, 1)
    per_page = max(min(per_page, 200), 1)
    sort = (sort or VinListingSort()).normalized()

    latest_customs = _latest_customs_subquery(db)
    matched = (
        db.query(CarListing, VinCustomsCheck)
        .outerjoin(latest_customs, func.upper(CarListing.vin) == latest_customs.c.vin)
        .outerjoin(VinCustomsCheck, VinCustomsCheck.id == latest_customs.c.max_id)
        .filter(
            CarListing.vin.isnot(None),
            func.length(CarListing.vin) == 17,
        )
        .all()
    )
    matched.sort(
        key=lambda row: _sort_key(row[0], row[1], sort.sort),
        reverse=sort.direction == "desc",
    )

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
