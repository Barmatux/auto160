"""Import-to-Belarus age filters for registered users on /listings."""

from __future__ import annotations

import calendar
import re
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session, Query

from app.models import CarListing, VinCustomsCheck
from app.vin_analytics import parse_filter_date

# Keep in sync with app.customs_vin.DATABASE_PERSONAL (avoid heavy import for tests).
CUSTOMS_DATABASE_PERSONAL = "personal_free_circulation"

IMPORT_AGE_RF_PASSABLE = "rf_passable"
IMPORT_AGE_OVER_10M = "import_over_10m"
IMPORT_AGE_RF_MONTHS = 12
IMPORT_AGE_OVER_10M_MONTHS = 10


def add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def normalize_import_age_filter(rf_passable: bool, import_over_10m: bool) -> str | None:
    """Return active filter key; RF passable wins if both are set."""
    if rf_passable:
        return IMPORT_AGE_RF_PASSABLE
    if import_over_10m:
        return IMPORT_AGE_OVER_10M
    return None


def import_age_min_months(filter_key: str | None) -> int | None:
    if filter_key == IMPORT_AGE_RF_PASSABLE:
        return IMPORT_AGE_RF_MONTHS
    if filter_key == IMPORT_AGE_OVER_10M:
        return IMPORT_AGE_OVER_10M_MONTHS
    return None


def release_date_older_than_months(release_date_raw: str | None, months: int, *, today: date | None = None) -> bool:
    parsed = parse_filter_date(release_date_raw)
    if parsed is None:
        return False
    cutoff = add_calendar_months(today or date.today(), -months)
    return parsed <= cutoff


def listing_has_saved_vin(listing: CarListing) -> bool:
    return len((listing.vin or "").strip()) == 17


def latest_release_dates_for_vins(db: Session, vins: set[str]) -> dict[str, str]:
    cleaned = {vin.strip().upper() for vin in vins if len((vin or "").strip()) == 17}
    if not cleaned:
        return {}
    rows = (
        db.query(VinCustomsCheck)
        .filter(
            VinCustomsCheck.vin.in_(cleaned),
            VinCustomsCheck.database == CUSTOMS_DATABASE_PERSONAL,
            VinCustomsCheck.found.is_(True),
            VinCustomsCheck.release_date.isnot(None),
        )
        .order_by(VinCustomsCheck.checked_at.desc())
        .all()
    )
    result: dict[str, str] = {}
    for row in rows:
        vin = (row.vin or "").strip().upper()
        if vin in result:
            continue
        release = (row.release_date or "").strip()
        if release:
            result[vin] = release
    return result


def apply_has_vin_sql_filter(query: Query) -> Query:
    vin_len = func.length(func.trim(CarListing.vin))
    return query.filter(CarListing.vin.isnot(None), vin_len == 17)


def paginate_query_with_import_age(
    db: Session,
    query: Query,
    *,
    min_months: int,
    page: int,
    page_size: int,
    today: date | None = None,
) -> tuple[list[CarListing], int]:
    """Apply VIN + release-date age filter with correct totals/pagination."""
    filtered_query = apply_has_vin_sql_filter(query)
    matched: list[CarListing] = []
    pending: list[CarListing] = []
    pending_vins: set[str] = set()
    today_value = today or date.today()

    def flush_pending() -> None:
        nonlocal pending, pending_vins
        if not pending:
            return
        release_by_vin = latest_release_dates_for_vins(db, pending_vins)
        for listing in pending:
            vin = (listing.vin or "").strip().upper()
            release = release_by_vin.get(vin)
            if release and release_date_older_than_months(release, min_months, today=today_value):
                matched.append(listing)
        pending = []
        pending_vins = set()

    for listing in filtered_query.yield_per(200):
        pending.append(listing)
        pending_vins.add((listing.vin or "").strip().upper())
        if len(pending) >= 200:
            flush_pending()
    flush_pending()

    total = len(matched)
    offset = max(page - 1, 0) * page_size
    return matched[offset : offset + page_size], total


def format_import_date_label(release_date: str | None) -> str | None:
    cleaned = (release_date or "").strip()
    if not cleaned:
        return None
    if re.search(r"г\.?\s*$", cleaned, flags=re.IGNORECASE):
        return f"Дата ввоза в РБ {cleaned}"
    return f"Дата ввоза в РБ {cleaned}г."
