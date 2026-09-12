"""Recompute brand/model/year average listing prices over rolling windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import statistics

from sqlalchemy.orm import Session

from app.listing_catalog_link import canonical_model_name, normalize_match_text
from app.models import CarListing, ListingAvgPrice, ListingStatus

DEFAULT_WINDOW_DAYS = 90
DEFAULT_WINDOWS = (30, 60, 90)
# Show / store only groups with more than 10 listings after outlier trim.
DEFAULT_MIN_SAMPLES = 11
IQR_K = 1.5


@dataclass(frozen=True)
class AvgPriceRecomputeStats:
    window_days: tuple[int, ...]
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


def trim_price_outliers(prices: list[float], *, k: float = IQR_K) -> tuple[list[float], int]:
    """Drop Tukey IQR outliers. Returns (kept_prices, removed_count).

    With fewer than 4 points IQR is unstable — keep the sample as-is.
    """
    if len(prices) < 4:
        return list(prices), 0
    try:
        q1, _, q3 = statistics.quantiles(prices, n=4, method="inclusive")
    except statistics.StatisticsError:
        return list(prices), 0
    iqr = q3 - q1
    if iqr <= 0:
        return list(prices), 0
    low = q1 - k * iqr
    high = q3 + k * iqr
    kept = [p for p in prices if low <= p <= high]
    if len(kept) < 3:
        # Too aggressive — fall back to raw sample.
        return list(prices), 0
    return kept, len(prices) - len(kept)


def recompute_listing_avg_prices(
    db: Session,
    *,
    window_days: int | None = None,
    windows: tuple[int, ...] | list[int] | None = None,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    now: datetime | None = None,
    trim_outliers: bool = True,
) -> AvgPriceRecomputeStats:
    """Replace listing_avg_prices for one or more rolling windows.

    Uses BYN prices (`CarListing.price`) where price_byn_missing is false.
    Includes published and archived ads (market observations); skips drafts.
    Prices outside Tukey IQR fences are dropped before averaging (optional).
    """
    window_end = now or datetime.utcnow()
    if windows is None:
        if window_days is not None:
            window_list = (max(1, int(window_days)),)
        else:
            window_list = tuple(max(1, int(d)) for d in DEFAULT_WINDOWS)
    else:
        window_list = tuple(sorted({max(1, int(d)) for d in windows}))
    if not window_list:
        window_list = DEFAULT_WINDOWS

    max_days = max(window_list)
    scan_start = window_end - timedelta(days=max_days)

    query = (
        db.query(
            CarListing.brand,
            CarListing.model,
            CarListing.year,
            CarListing.price,
            CarListing.created_at,
        )
        .filter(
            CarListing.created_at >= scan_start,
            CarListing.created_at <= window_end,
            CarListing.price.isnot(None),
            CarListing.price_byn_missing.is_(False),
            CarListing.status.in_([ListingStatus.published, ListingStatus.archived]),
        )
        .yield_per(1000)
    )

    # key -> (display_brand, display_model, year, [(created_at, price), ...])
    buckets: dict[tuple[str, str, int], list] = {}
    scanned = 0
    for brand, model, year, price, created_at in query:
        scanned += 1
        if year is None or price is None or created_at is None:
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
                [(created_at, price_f)],
            ]
        else:
            buckets[key][3].append((created_at, price_f))

    db.query(ListingAvgPrice).delete()
    written = 0
    for _key, (brand, model, year, observations) in buckets.items():
        for days in window_list:
            cutoff = window_end - timedelta(days=days)
            prices = [price for created_at, price in observations if created_at >= cutoff]
            raw_count = len(prices)
            if raw_count < min_samples:
                continue
            if trim_outliers:
                prices, removed = trim_price_outliers(prices)
            else:
                removed = 0
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
                sample_count_raw=raw_count,
                outliers_removed=removed,
                window_days=days,
                window_start=cutoff,
                window_end=window_end,
                computed_at=window_end,
            )
            db.add(row)
            written += 1

    db.commit()
    return AvgPriceRecomputeStats(
        window_days=window_list,
        listings_scanned=scanned,
        groups=len(buckets),
        rows_written=written,
        window_start=scan_start,
        window_end=window_end,
    )
