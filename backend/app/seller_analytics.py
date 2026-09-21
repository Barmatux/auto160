"""Admin analytics: business / legal-entity sellers grouped by seller_name."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote, urlencode

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.listing_avg_prices import DEFAULT_WINDOW_DAYS
from app.listing_catalog_link import canonical_model_name, normalize_match_text
from app.listing_display import format_money_amount, is_legal_entity_seller
from app.models import CarListing, ListingAvgPrice, ListingStatus

SORT_COLUMNS = (
    "name",
    "total",
    "published",
    "archived",
    "opened",
    "activity",
    "lifetime",
    "published_sum",
    "archived_sum",
    "vs_market",
)
DEFAULT_SORT = "archived_sum"
DEFAULT_DIR = "desc"
DESC_DEFAULT_COLUMNS = {
    "total",
    "published",
    "archived",
    "opened",
    "activity",
    "lifetime",
    "published_sum",
    "archived_sum",
    "vs_market",
}
# Treat |delta| under this % as "about market average".
NEAR_MARKET_PCT = 3.0

_WS_RE = re.compile(r"\s+")

AvgPriceMap = dict[tuple[str, str, int], float]


def normalize_seller_key(seller_name: str) -> str:
    return _WS_RE.sub(" ", seller_name.strip()).casefold()


def _listing_opened_at(listing: CarListing) -> datetime | None:
    return listing.avby_published_at or listing.created_at


def _listing_activity_at(listing: CarListing) -> datetime | None:
    return listing.avby_renewed_at or listing.avby_published_at or listing.created_at


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)


def listing_days_on_market(listing: CarListing, *, now: datetime | None = None) -> int | None:
    """Days the listing was/is on the market.

    Published: from open date until now («висит»).
    Archived: from open until last known activity (no archived_at in DB).
    """
    opened = _listing_opened_at(listing)
    if opened is None:
        return None
    opened = _as_naive_utc(opened)
    current = _as_naive_utc(now or datetime.utcnow())
    if listing.status == ListingStatus.archived:
        end = _listing_activity_at(listing)
        end = _as_naive_utc(end) if end is not None else opened
        if end < opened:
            end = opened
    else:
        end = current
    return max(0, (end - opened).days)


def format_days_label(days: int | None) -> str:
    if days is None:
        return "—"
    return f"{days} дн."


def format_listing_lifetime_label(listing: CarListing, days: int | None) -> str:
    if days is None:
        return "—"
    if listing.status == ListingStatus.archived:
        return f"прожило ~{days} дн."
    if listing.status == ListingStatus.published:
        return f"висит {days} дн."
    return f"{days} дн."


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


def _listing_avg_key(listing: CarListing) -> tuple[str, str, int] | None:
    brand_key = normalize_match_text(listing.brand or "")
    model_key = normalize_match_text(canonical_model_name(listing.model))
    if not brand_key or not model_key or listing.year is None:
        return None
    return brand_key, model_key, int(listing.year)


def load_avg_price_map(db: Session, *, window_days: int = DEFAULT_WINDOW_DAYS) -> AvgPriceMap:
    """brand/model/year -> avg BYN for the given rolling window."""
    rows = db.query(ListingAvgPrice).filter(ListingAvgPrice.window_days == int(window_days)).all()
    result: AvgPriceMap = {}
    for row in rows:
        brand_key = normalize_match_text(row.brand)
        model_key = normalize_match_text(canonical_model_name(row.model))
        if not brand_key or not model_key:
            continue
        try:
            avg = float(row.avg_price_byn)
        except (TypeError, ValueError):
            continue
        if avg <= 0:
            continue
        result[(brand_key, model_key, int(row.year))] = avg
    return result


def listing_vs_market_pct(listing: CarListing, avg_map: AvgPriceMap) -> float | None:
    """Positive = above market average, negative = below. None if no price or no avg."""
    price = _price_byn(listing)
    if price is None:
        return None
    key = _listing_avg_key(listing)
    if key is None:
        return None
    avg = avg_map.get(key)
    if avg is None or avg <= 0:
        return None
    return round((price - avg) / avg * 100.0, 1)


def format_vs_market_label(avg_pct: float | None, *, compared: int = 0) -> str:
    if avg_pct is None or compared <= 0:
        return "—"
    if abs(avg_pct) < NEAR_MARKET_PCT:
        return f"≈ рынок ({avg_pct:+.1f}%)"
    if avg_pct > 0:
        return f"выше рынка на {avg_pct:.1f}%"
    return f"ниже рынка на {abs(avg_pct):.1f}%"


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
    vs_market_compared: int = 0
    vs_market_above: int = 0
    vs_market_below: int = 0
    vs_market_near: int = 0
    vs_market_avg_pct: float | None = None
    avg_lifetime_days: float | None = None
    avg_hanging_days: float | None = None
    avg_archived_lifetime_days: float | None = None

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

    @property
    def vs_market_label(self) -> str:
        return format_vs_market_label(self.vs_market_avg_pct, compared=self.vs_market_compared)

    @property
    def vs_market_detail(self) -> str:
        if self.vs_market_compared <= 0:
            return "нет данных по рынку"
        return (
            f"сравнено {self.vs_market_compared}: "
            f"выше {self.vs_market_above} · ниже {self.vs_market_below} · ≈ {self.vs_market_near}"
        )

    @property
    def avg_lifetime_label(self) -> str:
        if self.avg_lifetime_days is None:
            return "—"
        return f"{self.avg_lifetime_days:.0f} дн."

    @property
    def lifetime_detail(self) -> str:
        parts: list[str] = []
        if self.avg_hanging_days is not None:
            parts.append(f"активные ср. {self.avg_hanging_days:.0f} дн.")
        if self.avg_archived_lifetime_days is not None:
            parts.append(f"архив ср. ~{self.avg_archived_lifetime_days:.0f} дн.")
        return " · ".join(parts) if parts else "нет дат"


@dataclass(frozen=True)
class BusinessSellerSummary:
    sellers_count: int
    listings_total: int
    published_total: int
    archived_total: int
    published_sum_byn: float
    archived_sum_byn: float
    vs_market_window_days: int = DEFAULT_WINDOW_DAYS

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
    market_avg_label: str = "—"
    vs_market_pct: float | None = None
    vs_market_label: str = "—"
    days_on_market: int | None = None
    lifetime_label: str = "—"


def _status_label(status: ListingStatus) -> str:
    if status == ListingStatus.published:
        return "Опубликовано"
    if status == ListingStatus.archived:
        return "В архиве"
    return "Черновик"


def _aggregate_seller(
    name: str,
    listings: list[CarListing],
    avg_map: AvgPriceMap | None = None,
    *,
    now: datetime | None = None,
) -> BusinessSellerStats:
    cities: set[str] = set()
    opened_at: datetime | None = None
    last_activity: datetime | None = None
    published = draft = archived = with_vin = with_photo = 0
    published_sum = archived_sum = 0.0
    published_priced = 0
    pcts: list[float] = []
    above = below = near = 0
    price_map = avg_map or {}
    lifetime_all: list[int] = []
    lifetime_published: list[int] = []
    lifetime_archived: list[int] = []
    current = now or datetime.utcnow()

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

        days = listing_days_on_market(listing, now=current)
        if days is not None and listing.status in (ListingStatus.published, ListingStatus.archived):
            lifetime_all.append(days)
            if listing.status == ListingStatus.published:
                lifetime_published.append(days)
            else:
                lifetime_archived.append(days)

        if listing.status in (ListingStatus.published, ListingStatus.archived):
            pct = listing_vs_market_pct(listing, price_map)
            if pct is None:
                continue
            pcts.append(pct)
            if abs(pct) < NEAR_MARKET_PCT:
                near += 1
            elif pct > 0:
                above += 1
            else:
                below += 1

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
        vs_market_compared=len(pcts),
        vs_market_above=above,
        vs_market_below=below,
        vs_market_near=near,
        vs_market_avg_pct=round(sum(pcts) / len(pcts), 1) if pcts else None,
        avg_lifetime_days=round(sum(lifetime_all) / len(lifetime_all), 1) if lifetime_all else None,
        avg_hanging_days=(
            round(sum(lifetime_published) / len(lifetime_published), 1) if lifetime_published else None
        ),
        avg_archived_lifetime_days=(
            round(sum(lifetime_archived) / len(lifetime_archived), 1) if lifetime_archived else None
        ),
    )


def _sort_key(row: BusinessSellerStats, sort: str):
    vs_key = row.vs_market_avg_pct if row.vs_market_avg_pct is not None else float("-inf")
    lifetime_key = row.avg_lifetime_days if row.avg_lifetime_days is not None else float("-inf")
    mapping = {
        "name": (row.seller_name.casefold(),),
        "total": (row.total, row.seller_name.casefold()),
        "published": (row.published, row.seller_name.casefold()),
        "archived": (row.archived, row.seller_name.casefold()),
        "opened": (row.opened_at or datetime.min, row.seller_name.casefold()),
        "activity": (row.last_activity_at or datetime.min, row.seller_name.casefold()),
        "lifetime": (lifetime_key, row.seller_name.casefold()),
        "published_sum": (row.published_sum_byn, row.seller_name.casefold()),
        "archived_sum": (row.archived_sum_byn, row.seller_name.casefold()),
        "vs_market": (vs_key, row.vs_market_compared, row.seller_name.casefold()),
    }
    return mapping.get(sort, mapping[DEFAULT_SORT])


def build_business_seller_report(
    db: Session,
    *,
    q: str | None = None,
    sort: BusinessSellerSort | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
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
    avg_map = load_avg_price_map(db, window_days=window_days)

    buckets: dict[str, list[CarListing]] = {}
    display_names: dict[str, str] = {}
    for listing in listings:
        raw = (listing.seller_name or "").strip()
        if not is_legal_entity_seller(raw):
            continue
        key = normalize_seller_key(raw)
        buckets.setdefault(key, []).append(listing)
        prev = display_names.get(key)
        if prev is None or len(raw) > len(prev):
            display_names[key] = raw

    query = (q or "").strip().casefold()
    rows = [
        _aggregate_seller(display_names[key], group, avg_map)
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
        vs_market_window_days=window_days,
    )
    return summary, rows


def build_business_seller_listings(
    db: Session,
    seller_name: str,
    *,
    limit: int = 200,
    window_days: int = DEFAULT_WINDOW_DAYS,
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

    avg_map = load_avg_price_map(db, window_days=window_days)
    display = max((listing.seller_name or "").strip() for listing in matched)
    stats = _aggregate_seller(display, matched, avg_map)
    matched.sort(
        key=lambda listing: _listing_activity_at(listing) or datetime.min,
        reverse=True,
    )
    rows: list[BusinessSellerListingRow] = []
    for listing in matched[:limit]:
        price = _price_byn(listing)
        avg_key = _listing_avg_key(listing)
        market_avg = avg_map.get(avg_key) if avg_key else None
        pct = listing_vs_market_pct(listing, avg_map)
        days = listing_days_on_market(listing)
        rows.append(
            BusinessSellerListingRow(
                listing=listing,
                opened_at=_listing_opened_at(listing),
                activity_at=_listing_activity_at(listing),
                price_label=format_money_amount(price) if price is not None else "—",
                status_label=_status_label(listing.status),
                market_avg_label=format_money_amount(market_avg) if market_avg is not None else "—",
                vs_market_pct=pct,
                vs_market_label=format_vs_market_label(pct, compared=1 if pct is not None else 0),
                days_on_market=days,
                lifetime_label=format_listing_lifetime_label(listing, days),
            )
        )
    return stats, rows
