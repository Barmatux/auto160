"""EU «проходные» age window: first registration between 2y8m and 4y10m ago."""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Any

from sqlalchemy.orm import Query

# Buffer before the 3y floor and before the 5y ceiling.
PASSABLE_AGE_MIN_MONTHS = 2 * 12 + 8  # 2 years 8 months
PASSABLE_AGE_MAX_MONTHS = 4 * 12 + 10  # 4 years 10 months

_REG_YM_MARKED = re.compile(r"((?:19|20)\d{2})-(0[1-9]|1[0-2])\s*m\.", re.IGNORECASE)
_REG_YM_BARE = re.compile(r"(?<!\d)((?:19|20)\d{2})-(0[1-9]|1[0-2])(?!\d)")


def _add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def passable_registration_window(*, today: date | None = None) -> tuple[date, date]:
    """Inclusive first-registration dates that fall in the passable age window.

    Age in [2y8m, 4y10m] ⇔ registration in [today-4y10m, today-2y8m].
    """
    today_value = today or date.today()
    start = _add_calendar_months(today_value, -PASSABLE_AGE_MAX_MONTHS)
    end = _add_calendar_months(today_value, -PASSABLE_AGE_MIN_MONTHS)
    return start, end


def registration_date_for_listing(listing: Any) -> date | None:
    """Best-effort first-registration date: YYYY-MM from title, else None (year-only handled separately)."""
    title = getattr(listing, "title", None) or ""
    match = _REG_YM_MARKED.search(title) or _REG_YM_BARE.search(title)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), 1)
    except ValueError:
        return None


def listing_matches_passable_age(listing: Any, *, today: date | None = None) -> bool:
    start, end = passable_registration_window(today=today)
    reg = registration_date_for_listing(listing)
    if reg is not None:
        return start <= reg <= end
    year = getattr(listing, "year", None)
    if year is None:
        return False
    # Year-only: keep if any day of that year overlaps the window.
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    return year_start <= end and year_end >= start


def apply_passable_age_year_prefilter(query: Query, *, today: date | None = None) -> Query:
    """Narrow by calendar year before exact age matching."""
    from app.models import CarListing

    start, end = passable_registration_window(today=today)
    return query.filter(
        CarListing.year.isnot(None),
        CarListing.year >= start.year,
        CarListing.year <= end.year,
    )


def paginate_query_with_passable_age(
    query: Query,
    *,
    page: int,
    page_size: int,
    today: date | None = None,
) -> tuple[list[Any], int]:
    """Filter to passable age with correct totals/pagination."""
    filtered = apply_passable_age_year_prefilter(query, today=today)
    matched = [
        listing
        for listing in filtered.yield_per(200)
        if listing_matches_passable_age(listing, today=today)
    ]
    total = len(matched)
    offset = max(page - 1, 0) * page_size
    return matched[offset : offset + page_size], total
