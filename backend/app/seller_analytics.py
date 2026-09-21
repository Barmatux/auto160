"""Admin analytics: business / legal-entity sellers grouped by seller_name."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote, urlencode

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.listing_display import format_money_amount, is_legal_entity_seller
from app.models import CarListing, ListingStatus

SORT_COLUMNS = (
    "name",
    "total",
    "published",
    "archived",
    "opened",
    "activity",
    "published_sum",
    "archived_sum",
)
DEFAULT_SORT = "archived_sum"
DEFAULT_DIR = "desc"
DESC_DEFAULT_COLUMNS = {
    "total",
    "published",
    "archived",
    "opened",
    "activity",
    "published_sum",
    "archived_sum",
}

_WS_RE = re.compile(r"\s+")


def normalize_seller_key(seller_name: str) -> str:
    return _WS_RE.sub(" ", seller_name.strip()).casefold()


def _listing_opened_at(listing: CarListing) -> datetime | None:
    return listing.avby_published_at or listing.created_at


def _listing_activity_at(listing: CarListing) -> datetime | None:
    return listing.avby_renewed_at or listing.avby_published_at or listing.created_at


def _price_byn(listing: CarListing) -> float | None:
    if listing.price is None or listing.price_byn_missing:
        return None
    try:
        value = float(listing.price)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


@dataclass(frozen=True)
class BusinessSellerSort:
    sort: str = DEFAULT_SORT
    direction: str = DEFAULT_DIR

    def normalized(self) -> "BusinessSellerSort":
        sort = self.sort if self.sort in SORT_COLUMNS else DEFAULT_SORT
        direction = "asc" if self.direction == "asc" else "desc"
        return BusinessSellerSort(sort=sort, direction=direction)

    def query_pairs(
        self,
        *,
        q: str | None = None,
        page: int | None = None,
        seller: str | None = None,
    ) -> list[tuple[str, str]]:
        current = self.normalized()
        pairs: list[tuple[str, str]] = []
        if q:
            pairs.append(("q", q))
        if seller:
            pairs.append(("seller", seller))
        if current.sort != DEFAULT_SORT:
            pairs.append(("sort", current.sort))
        if current.direction != DEFAULT_DIR or current.sort != DEFAULT_SORT:
            pairs.append(("dir", current.direction))
        if page and page > 1:
            pairs.append(("page", str(page)))
        return pairs

    def query_string(
        self,
        *,
        q: str | None = None,
        page: int | None = None,
        seller: str | None = None,
    ) -> str:
        return urlencode(self.query_pairs(q=q, page=page, seller=seller))

    def toggle_url(self, column: str, *, q: str | None = None) -> str:
        current = self.normalized()
        if column == current.sort:
            next_dir = "asc" if current.direction == "desc" else "desc"
        else:
            next_dir = "desc" if column in DESC_DEFAULT_COLUMNS else "asc"
        return BusinessSellerSort(sort=column, direction=next_dir).query_string(q=q)

    def arrow(self, column: str) -> str:
        current = self.normalized()
        if column != current.sort:
            return "↕"
        return "↓" if current.direction == "desc" else "↑"


@dataclass
class BusinessSellerStats:
    seller_name: str
    total: int = 0
    published: int = 0
    draft: int = 0
    archived: int = 0
    with_vin: int = 0
    with_photo: int = 0
    cities: int = 0
    opened_at: datetime | None = None
    last_activity_at: datetime | None = None
    published_sum_byn: float = 0.0
    archived_sum_byn: float = 0.0
    published_avg_byn: float | None = None
    city_names: tuple[str, ...] = ()

    @property
    def detail_url(self) -> str:
        return f"/admin/business-sellers?seller={quote(self.seller_name, safe='')}"

    @property
    def published_sum_label(self) -> str:
        return format_money_amount(self.published_sum_byn) if self.published_sum_byn else "—"

    @property
    def archived_sum_label(self) -> str:
        return format_money_amount(self.archived_sum_byn) if self.archived_sum_byn else "—"

    @property
    def published_avg_label(self) -> str:
        return format_money_amount(self.published_avg_byn) if self.published_avg_byn is not None else "—"


@dataclass(frozen=True)
class BusinessSellerSummary:
    sellers_count: int
    listings_total: int
    published_total: int
    archived_total: int
    published_sum_byn: float
    archived_sum_byn: float

    @property
    def published_sum_label(self) -> str:
        return format_money_amount(self.published_sum_byn) if self.published_sum_byn else "—"

    @property
    def archived_sum_label(self) -> str:
        return format_money_amount(self.archived_sum_byn) if self.archived_sum_byn else "—"


@dataclass(frozen=True)
class BusinessSellerListingRow:
    listing: CarListing
    opened_at: datetime | None
    activity_at: datetime | None
    price_label: str
    status_label: str


def _status_label(status: ListingStatus) -> str:
    if status == ListingStatus.published:
        return "Опубликовано"
    if status == ListingStatus.archived:
        return "В архиве"
    return "Черновик"


def _aggregate_seller(name: str, listings: list[CarListing]) -> BusinessSellerStats:
    cities: set[str] = set()
    opened_at: datetime | None = None
    last_activity: datetime | None = None
    published = draft = archived = with_vin = with_photo = 0
    published_sum = archived_sum = 0.0
    published_priced = 0

    for listing in listings:
        city = (listing.city or "").strip()
        if city:
            cities.add(city)
        opened = _listing_opened_at(listing)
        activity = _listing_activity_at(listing)
        if opened and (opened_at is None or opened < opened_at):
            opened_at = opened
        if activity and (last_activity is None or activity > last_activity):
            last_activity = activity
        if listing.vin:
            with_vin += 1
        if (listing.cover_photo_url or "").strip() or listing.raw_photos:
            with_photo += 1

        price = _price_byn(listing)
        if listing.status == ListingStatus.published:
            published += 1
            if price is not None:
                published_sum += price
                published_priced += 1
        elif listing.status == ListingStatus.archived:
            archived += 1
            if price is not None:
                archived_sum += price
        else:
            draft += 1

    return BusinessSellerStats(
        seller_name=name,
        total=len(listings),
        published=published,
        draft=draft,
        archived=archived,
        with_vin=with_vin,
        with_photo=with_photo,
        cities=len(cities),
        opened_at=opened_at,
        last_activity_at=last_activity,
        published_sum_byn=round(published_sum, 2),
        archived_sum_byn=round(archived_sum, 2),
        published_avg_byn=round(published_sum / published_priced, 2) if published_priced else None,
        city_names=tuple(sorted(cities)),
    )


def _sort_key(row: BusinessSellerStats, sort: str):
    mapping = {
        "name": (row.seller_name.casefold(),),
        "total": (row.total, row.seller_name.casefold()),
        "published": (row.published, row.seller_name.casefold()),
        "archived": (row.archived, row.seller_name.casefold()),
        "opened": (row.opened_at or datetime.min, row.seller_name.casefold()),
        "activity": (row.last_activity_at or datetime.min, row.seller_name.casefold()),
        "published_sum": (row.published_sum_byn, row.seller_name.casefold()),
        "archived_sum": (row.archived_sum_byn, row.seller_name.casefold()),
    }
    return mapping.get(sort, mapping[DEFAULT_SORT])


def build_business_seller_report(
    db: Session,
    *,
    q: str | None = None,
    sort: BusinessSellerSort | None = None,
) -> tuple[BusinessSellerSummary, list[BusinessSellerStats]]:
    """Group av.by listings by legal-entity seller_name and compute inventory / archive stats."""
    listings = (
        db.query(CarListing)
        .filter(
            CarListing.seller_name.isnot(None),
            CarListing.seller_name != "",
            or_(CarListing.source.is_(None), CarListing.source == "av.by"),
        )
        .all()
    )

    buckets: dict[str, list[CarListing]] = {}
    display_names: dict[str, str] = {}
    for listing in listings:
        raw = (listing.seller_name or "").strip()
        if not is_legal_entity_seller(raw):
            continue
        key = normalize_seller_key(raw)
        buckets.setdefault(key, []).append(listing)
        # Prefer longer / more complete display label when casing differs.
        prev = display_names.get(key)
        if prev is None or len(raw) > len(prev):
            display_names[key] = raw

    query = (q or "").strip().casefold()
    rows = [
        _aggregate_seller(display_names[key], group)
        for key, group in buckets.items()
        if not query or query in display_names[key].casefold()
    ]

    current = (sort or BusinessSellerSort()).normalized()
    reverse = current.direction == "desc"
    rows.sort(key=lambda row: _sort_key(row, current.sort), reverse=reverse)

    summary = BusinessSellerSummary(
        sellers_count=len(rows),
        listings_total=sum(r.total for r in rows),
        published_total=sum(r.published for r in rows),
        archived_total=sum(r.archived for r in rows),
        published_sum_byn=round(sum(r.published_sum_byn for r in rows), 2),
        archived_sum_byn=round(sum(r.archived_sum_byn for r in rows), 2),
    )
    return summary, rows


def build_business_seller_listings(
    db: Session,
    seller_name: str,
    *,
    limit: int = 200,
) -> tuple[BusinessSellerStats | None, list[BusinessSellerListingRow]]:
    key = normalize_seller_key(seller_name)
    if not key:
        return None, []

    listings = (
        db.query(CarListing)
        .filter(
            CarListing.seller_name.isnot(None),
            CarListing.seller_name != "",
            or_(CarListing.source.is_(None), CarListing.source == "av.by"),
        )
        .order_by(CarListing.id.desc())
        .all()
    )
    matched = [
        listing
        for listing in listings
        if normalize_seller_key(listing.seller_name or "") == key and is_legal_entity_seller(listing.seller_name)
    ]
    if not matched:
        return None, []

    display = max((listing.seller_name or "").strip() for listing in matched)
    stats = _aggregate_seller(display, matched)
    matched.sort(
        key=lambda listing: _listing_activity_at(listing) or datetime.min,
        reverse=True,
    )
    rows = [
        BusinessSellerListingRow(
            listing=listing,
            opened_at=_listing_opened_at(listing),
            activity_at=_listing_activity_at(listing),
            price_label=format_money_amount(_price_byn(listing)) if _price_byn(listing) is not None else "—",
            status_label=_status_label(listing.status),
        )
        for listing in matched[:limit]
    ]
    return stats, rows
