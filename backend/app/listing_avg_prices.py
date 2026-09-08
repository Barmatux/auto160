"""Recompute brand/model/year average listing prices over a rolling window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.listing_catalog_link import canonical_model_name, normalize_match_text
from app.models import CarListing, ListingAvgPrice, ListingStatus

DEFAULT_WINDOW_DAYS = 90
MIN_SAMPLE_COUNT = 1


@dataclass(frozen=True)
class AvgPriceRecomputeStats:
    window_days: int
    listings_scanned: int
    groups: int
    rows_written: int
    window_start: datetime
    window_end: datetime


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _canonical_brand(brand: str) -> str:
    cleaned = (brand or "").strip()
    if not cleaned:
        return ""
    # Keep common ALLCAPS brands (BMW, Kia) but title-case mixed junk.
    if cleaned.isupper() and len(cleaned) <= 5:
        return cleaned
    return cleaned[:1].upper() + cleaned[1:]


def recompute_listing_avg_prices(
    db: Session,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_samples: int = MIN_SAMPLE_COUNT,
    now: datetime | None = None,
) -> AvgPriceRecomputeStats:
    """Replace listing_avg_prices from listings created in the last window_days.

    Uses BYN prices (`CarListing.price`) where price_byn_missing is false.
    Includes published and archived ads (market observations); skips drafts.
    """
    window_end = now or datetime.utcnow()
    days = max(1, int(window_days))
    window_start = window_end - timedelta(days=days)

    query = (
        db.query(
            CarListing.brand,
            CarListing.model,
            CarListing.year,
            CarListing.price,
        )
        .filter(
            CarListing.created_at >= window_start,
            CarListing.created_at <= window_end,
            CarListing.price.isnot(None),
            CarListing.price_byn_missing.is_(False),
            CarListing.status.in_([ListingStatus.published, ListingStatus.archived]),
        )
        .yield_per(1000)
    )

    # key -> (display_brand, display_model, year, prices)
    buckets: dict[tuple[str, str, int], list] = {}
    scanned = 0
    for brand, model, year, price in query:
        scanned += 1
        if year is None or price is None:
            continue
        brand_key = normalize_match_text(brand)
        model_key = normalize_match_text(canonical_model_name(model))
        if not brand_key or not model_key:
            continue
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            continue
        if price_f <= 0:
            continue
        key = (brand_key, model_key, int(year))
        if key not in buckets:
            buckets[key] = [
                _canonical_brand(brand or ""),
                canonical_model_name(model) or (model or "").strip(),
                int(year),
                [price_f],
            ]
        else:
            buckets[key][3].append(price_f)

    db.query(ListingAvgPrice).delete()
    written = 0
    for _key, (brand, model, year, prices) in buckets.items():
        if len(prices) < min_samples:
            continue
        avg = sum(prices) / len(prices)
        row = ListingAvgPrice(
            brand=brand,
            model=model,
            year=year,
            avg_price_byn=_money(avg),
            min_price_byn=_money(min(prices)),
            max_price_byn=_money(max(prices)),
            sample_count=len(prices),
            window_days=days,
            window_start=window_start,
            window_end=window_end,
            computed_at=window_end,
        )
        db.add(row)
        written += 1

    db.commit()
    return AvgPriceRecomputeStats(
        window_days=days,
        listings_scanned=scanned,
        groups=len(buckets),
        rows_written=written,
        window_start=window_start,
        window_end=window_end,
    )
