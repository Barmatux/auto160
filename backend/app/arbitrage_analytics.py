"""EU→BY niche velocity analytics from av.by ocenka sold samples."""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.avby_price_stats import catalog_slug_from_url
from app.exchange_rates import fetch_nbrb_rates
from app.models import (
    AvbyPriceHistoryPoint,
    AvbyPriceSoldAdvert,
    AvbyPriceStatTarget,
    AvbyPriceYearStat,
    CarListing,
    CatalogItem,
    ListingStatus,
)

_EU_SOURCES = ("autoplius", "auto24", "mobile_de")
_CACHE_TTL_SEC = 900
_cache: dict[str, Any] = {"key": None, "expires": 0.0, "rows": None, "kpi": None}

DEFAULT_MAX_HP = 160
DEFAULT_MAX_PRICE_USD = 20_000
DEFAULT_MIN_SOLD_N = 8


def _num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def _median(vals: list[float]) -> float | None:
    return _percentile(sorted(vals), 0.5)


def _linear_slope(ys: list[float]) -> float | None:
    """Simple OLS slope vs index 0..n-1; positive = price rising."""
    n = len(ys)
    if n < 2:
        return None
    x_mean = (n - 1) / 2.0
    y_mean = sum(ys) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(ys))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den <= 0:
        return None
    return num / den


def hp_by_catalog_slug(db: Session) -> dict[str, int]:
    """Min engine_power_hp per ocenka catalog slug (rating=1 catalog rows)."""
    items = (
        db.query(CatalogItem.source_url, CatalogItem.engine_power_hp)
        .filter(CatalogItem.rating == 1)
        .filter(CatalogItem.engine_power_hp.isnot(None))
        .filter(
            (CatalogItem.source_site == "av.by")
            | (CatalogItem.source_url.ilike("%av.by/catalog/%"))
        )
        .all()
    )
    out: dict[str, int] = {}
    for source_url, hp in items:
        slug = catalog_slug_from_url(source_url)
        if not slug or hp is None:
            continue
        hp_i = int(hp)
        prev = out.get(slug)
        if prev is None or hp_i < prev:
            out[slug] = hp_i
    return out


@dataclass(frozen=True)
class NicheRow:
    year_stat_id: int
    target_id: int
    make: str
    model: str
    generation: str
    year: int
    hp: int
    catalog_slug: str
    median_days: float
    p25_days: float
    pct_sold_le_14: float
    pct_sold_le_30: float
    sold_n: int
    active_n: int | None
    removed_60d: int | None
    new_60d: int | None
    turnover_60d: float | None
    median_price_usd: float
    price_p25_usd: float | None
    price_p75_usd: float | None
    price_iqr_usd: float | None
    price_trend_6m: float | None
    velocity_score: float
    main_filter_url: str | None
    image_url: str | None
    year_stat_price_usd: float | None

    @property
    def label(self) -> str:
        gen = self.generation if self.generation != "—" else ""
        base = f"{self.make} {self.model}".strip()
        if gen:
            return f"{base} · {gen} · {self.year}"
        return f"{base} · {self.year}"

    @property
    def detail_url(self) -> str:
        return f"/admin/arbitrage/{self.year_stat_id}"

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["label"] = self.label
        d["detail_url"] = self.detail_url
        return d


@dataclass(frozen=True)
class ArbitrageFilters:
    max_hp: int = DEFAULT_MAX_HP
    max_price_usd: float = DEFAULT_MAX_PRICE_USD
    min_sold_n: int = DEFAULT_MIN_SOLD_N
    max_median_days: float | None = None
    year_from: int | None = None
    year_to: int | None = None
    make: str | None = None
    q: str | None = None

    def cache_key(self) -> str:
        return (
            f"{self.max_hp}|{self.max_price_usd}|{self.min_sold_n}|"
            f"{self.max_median_days}|{self.year_from}|{self.year_to}|"
            f"{self.make}|{self.q}"
        )


def _score_niche(
    *,
    median_days: float,
    pct_sold_le_30: float,
    turnover_60d: float | None,
    sold_n: int,
    active_n: int | None,
    turnover_cap: float,
) -> float:
    # Faster days → higher; cap at 90 days.
    days_norm = 1.0 - min(max(median_days, 0.0), 90.0) / 90.0
    pct_norm = min(max(pct_sold_le_30, 0.0), 1.0)
    if turnover_60d is None or turnover_cap <= 0:
        turn_norm = 0.0
    else:
        turn_norm = min(max(turnover_60d, 0.0), turnover_cap) / turnover_cap
    sold_norm = min(math.log1p(sold_n) / math.log1p(40), 1.0)

    raw = 100.0 * (
        0.40 * days_norm + 0.25 * pct_norm + 0.20 * turn_norm + 0.15 * sold_norm
    )
    # Overstock penalty: many active ads + slow median.
    if active_n is not None and active_n >= 25 and median_days >= 45:
        raw -= 15.0
    confidence = 1.0 if sold_n >= 20 else sold_n / 20.0
    return round(max(0.0, min(100.0, raw * confidence)), 1)


def _compute_all_niches(db: Session) -> list[NicheRow]:
    hp_map = hp_by_catalog_slug(db)
    year_stats = (
        db.query(AvbyPriceYearStat)
        .options(joinedload(AvbyPriceYearStat.target))
        .filter(AvbyPriceYearStat.fetch_status == "ok")
        .all()
    )
    if not year_stats:
        return []

    year_stat_ids = [ys.id for ys in year_stats]
    sold_rows = (
        db.query(AvbyPriceSoldAdvert)
        .filter(AvbyPriceSoldAdvert.year_stat_id.in_(year_stat_ids))
        .all()
    )
    sold_by_ys: dict[int, list[AvbyPriceSoldAdvert]] = {}
    for advert in sold_rows:
        sold_by_ys.setdefault(advert.year_stat_id, []).append(advert)

    history_rows = (
        db.query(AvbyPriceHistoryPoint)
        .filter(AvbyPriceHistoryPoint.year_stat_id.in_(year_stat_ids))
        .order_by(
            AvbyPriceHistoryPoint.year_stat_id.asc(),
            AvbyPriceHistoryPoint.year.asc(),
            AvbyPriceHistoryPoint.month.asc(),
        )
        .all()
    )
    hist_by_ys: dict[int, list[float]] = {}
    for point in history_rows:
        val = _num(point.median_price_usd)
        if val is None:
            continue
        hist_by_ys.setdefault(point.year_stat_id, []).append(val)

    # Precompute turnover distribution for cap (p95 among positive turnovers).
    turnovers: list[float] = []
    for ys in year_stats:
        active = ys.active_advert_count
        removed = ys.activity_removed_60d
        if active is None or removed is None:
            continue
        turnovers.append(float(removed) / max(int(active), 1))
    turnovers.sort()
    turnover_cap = _percentile(turnovers, 0.95) if turnovers else 2.0
    if turnover_cap is None or turnover_cap <= 0:
        turnover_cap = 2.0

    niches: list[NicheRow] = []
    for ys in year_stats:
        target = ys.target
        if target is None:
            continue
        hp = hp_map.get(target.catalog_slug)
        if hp is None:
            continue

        adverts = sold_by_ys.get(ys.id) or []
        days_list = [
            float(a.days_on_sale)
            for a in adverts
            if a.days_on_sale is not None and a.days_on_sale >= 0
        ]
        price_list = [
            p
            for a in adverts
            if (p := _num(a.price_usd)) is not None and p > 0
        ]
        if not days_list:
            continue

        days_sorted = sorted(days_list)
        median_days = _percentile(days_sorted, 0.5)
        p25_days = _percentile(days_sorted, 0.25)
        if median_days is None or p25_days is None:
            continue

        sold_n = len(days_list)
        pct14 = sum(1 for d in days_list if d <= 14) / sold_n
        pct30 = sum(1 for d in days_list if d <= 30) / sold_n

        median_price = _median(price_list)
        if median_price is None:
            median_price = _num(ys.price_usd)
        if median_price is None or median_price <= 0:
            continue

        prices_sorted = sorted(price_list) if price_list else []
        p25_price = _percentile(prices_sorted, 0.25) if prices_sorted else None
        p75_price = _percentile(prices_sorted, 0.75) if prices_sorted else None
        iqr = None
        if p25_price is not None and p75_price is not None:
            iqr = p75_price - p25_price

        active_n = ys.active_advert_count
        removed = ys.activity_removed_60d
        new_60 = ys.activity_new_60d
        turnover = None
        if active_n is not None and removed is not None:
            turnover = float(removed) / max(int(active_n), 1)

        hist_vals = hist_by_ys.get(ys.id) or []
        trend = _linear_slope(hist_vals[-6:]) if hist_vals else None

        score = _score_niche(
            median_days=median_days,
            pct_sold_le_30=pct30,
            turnover_60d=turnover,
            sold_n=sold_n,
            active_n=int(active_n) if active_n is not None else None,
            turnover_cap=float(turnover_cap),
        )

        niches.append(
            NicheRow(
                year_stat_id=ys.id,
                target_id=target.id,
                make=target.make or (ys.make or ""),
                model=target.model or (ys.model_name or ""),
                generation=(target.generation or ys.generation_name or "—"),
                year=ys.year,
                hp=hp,
                catalog_slug=target.catalog_slug,
                median_days=round(median_days, 1),
                p25_days=round(p25_days, 1),
                pct_sold_le_14=round(pct14, 3),
                pct_sold_le_30=round(pct30, 3),
                sold_n=sold_n,
                active_n=int(active_n) if active_n is not None else None,
                removed_60d=int(removed) if removed is not None else None,
                new_60d=int(new_60) if new_60 is not None else None,
                turnover_60d=round(turnover, 3) if turnover is not None else None,
                median_price_usd=round(median_price, 0),
                price_p25_usd=round(p25_price, 0) if p25_price is not None else None,
                price_p75_usd=round(p75_price, 0) if p75_price is not None else None,
                price_iqr_usd=round(iqr, 0) if iqr is not None else None,
                price_trend_6m=round(trend, 2) if trend is not None else None,
                velocity_score=score,
                main_filter_url=ys.main_filter_url,
                image_url=ys.image_url,
                year_stat_price_usd=_num(ys.price_usd),
            )
        )
    return niches


def filter_niches(rows: list[NicheRow], filters: ArbitrageFilters) -> list[NicheRow]:
    q = (filters.q or "").strip().lower() or None
    make = (filters.make or "").strip() or None
    out: list[NicheRow] = []
    for row in rows:
        if row.hp > filters.max_hp:
            continue
        if row.median_price_usd > filters.max_price_usd:
            continue
        if row.sold_n < filters.min_sold_n:
            continue
        if filters.max_median_days is not None and row.median_days > filters.max_median_days:
            continue
        if filters.year_from is not None and row.year < filters.year_from:
            continue
        if filters.year_to is not None and row.year > filters.year_to:
            continue
        if make and row.make != make:
            continue
        if q:
            blob = f"{row.make} {row.model} {row.generation} {row.catalog_slug}".lower()
            if q not in blob:
                continue
        out.append(row)
    out.sort(key=lambda r: (-r.velocity_score, r.median_days, -r.sold_n))
    return out


def build_kpi(rows: list[NicheRow]) -> dict[str, Any]:
    if not rows:
        return {
            "niches_count": 0,
            "top20_median_days": None,
            "top20_median_days_label": "—",
            "fast_share_le_21": 0.0,
            "fast_share_label": "0%",
            "avg_score": None,
            "avg_score_label": "—",
        }
    top20 = rows[:20]
    top_days = [r.median_days for r in top20]
    top_med = _median(top_days)
    fast_n = sum(1 for r in rows if r.median_days <= 21)
    fast_share = fast_n / len(rows)
    avg_score = sum(r.velocity_score for r in rows) / len(rows)
    return {
        "niches_count": len(rows),
        "top20_median_days": round(top_med, 1) if top_med is not None else None,
        "top20_median_days_label": (
            f"{top_med:.0f} дн." if top_med is not None else "—"
        ),
        "fast_share_le_21": round(fast_share, 3),
        "fast_share_label": f"{fast_share * 100:.0f}%",
        "avg_score": round(avg_score, 1),
        "avg_score_label": f"{avg_score:.0f}",
    }


def list_arbitrage_niches(
    db: Session,
    filters: ArbitrageFilters,
    *,
    use_cache: bool = True,
) -> tuple[list[NicheRow], dict[str, Any]]:
    key = filters.cache_key()
    now = time.monotonic()
    if (
        use_cache
        and _cache["key"] == key
        and _cache["expires"] > now
        and _cache["rows"] is not None
    ):
        return list(_cache["rows"]), dict(_cache["kpi"])

    # Broader cache: compute unfiltered once, then filter.
    base_key = "__all__"
    if (
        use_cache
        and _cache.get("base_key") == base_key
        and _cache.get("base_expires", 0) > now
        and _cache.get("base_rows") is not None
    ):
        all_rows: list[NicheRow] = list(_cache["base_rows"])
    else:
        all_rows = _compute_all_niches(db)
        if use_cache:
            _cache["base_key"] = base_key
            _cache["base_expires"] = now + _CACHE_TTL_SEC
            _cache["base_rows"] = all_rows

    filtered = filter_niches(all_rows, filters)
    kpi = build_kpi(filtered)
    if use_cache:
        _cache["key"] = key
        _cache["expires"] = now + _CACHE_TTL_SEC
        _cache["rows"] = filtered
        _cache["kpi"] = kpi
    return filtered, kpi


def list_arbitrage_makes(db: Session, filters: ArbitrageFilters) -> list[str]:
    # Makes from filtered universe without make/q constraints.
    base = ArbitrageFilters(
        max_hp=filters.max_hp,
        max_price_usd=filters.max_price_usd,
        min_sold_n=filters.min_sold_n,
        max_median_days=filters.max_median_days,
        year_from=filters.year_from,
        year_to=filters.year_to,
    )
    rows, _ = list_arbitrage_niches(db, base)
    return sorted({r.make for r in rows if r.make})


def chart_payload(rows: list[NicheRow], *, top_n: int = 15) -> dict[str, Any]:
    top = rows[:top_n]
    return {
        "bar": {
            "labels": [r.label for r in reversed(top)],
            "scores": [r.velocity_score for r in reversed(top)],
            "ids": [r.year_stat_id for r in reversed(top)],
        },
        "scatter": {
            "points": [
                {
                    "x": r.median_days,
                    "y": r.median_price_usd,
                    "r": max(4, min(18, 3 + r.sold_n * 0.35)),
                    "label": r.label,
                    "score": r.velocity_score,
                    "url": r.detail_url,
                }
                for r in rows[:80]
            ]
        },
    }


def get_niche_detail(db: Session, year_stat_id: int) -> dict[str, Any] | None:
    ys = (
        db.query(AvbyPriceYearStat)
        .options(
            joinedload(AvbyPriceYearStat.target),
            joinedload(AvbyPriceYearStat.sold_adverts),
            joinedload(AvbyPriceYearStat.history_points),
        )
        .filter(AvbyPriceYearStat.id == year_stat_id)
        .first()
    )
    if ys is None or ys.target is None:
        return None

    hp_map = hp_by_catalog_slug(db)
    hp = hp_map.get(ys.target.catalog_slug)

    # Build single-row metrics via shared path when possible.
    all_rows, _ = list_arbitrage_niches(
        db,
        ArbitrageFilters(
            max_hp=10_000,
            max_price_usd=10_000_000,
            min_sold_n=1,
        ),
    )
    row = next((r for r in all_rows if r.year_stat_id == year_stat_id), None)

    days_list = [
        int(a.days_on_sale)
        for a in ys.sold_adverts
        if a.days_on_sale is not None and a.days_on_sale >= 0
    ]
    # Histogram buckets
    buckets = [0, 7, 14, 21, 30, 45, 60, 90, 120, 180, 365]
    hist_labels: list[str] = []
    hist_counts: list[int] = []
    for i in range(len(buckets) - 1):
        lo, hi = buckets[i], buckets[i + 1]
        hist_labels.append(f"{lo}–{hi}")
        hist_counts.append(sum(1 for d in days_list if lo <= d < hi))
    hist_labels.append(f"{buckets[-1]}+")
    hist_counts.append(sum(1 for d in days_list if d >= buckets[-1]))

    history = sorted(ys.history_points, key=lambda p: (p.year, p.month))
    hist_labels_line = [f"{p.month:02d}.{p.year}" for p in history if _num(p.median_price_usd)]
    hist_values_line = [
        round(v, 0)
        for p in history
        if (v := _num(p.median_price_usd)) is not None
    ]

    sold_table = []
    for advert in sorted(
        ys.sold_adverts,
        key=lambda a: a.published_at or datetime.min,
        reverse=True,
    )[:40]:
        sold_table.append(
            {
                "avby_id": advert.avby_id,
                "price_usd": _num(advert.price_usd),
                "price_usd_label": (
                    f"{_num(advert.price_usd):,.0f} $".replace(",", " ")
                    if _num(advert.price_usd) is not None
                    else "—"
                ),
                "days_on_sale": advert.days_on_sale if advert.days_on_sale is not None else "—",
                "published_at": advert.published_at,
                "published_label": (
                    advert.published_at.strftime("%d.%m.%Y") if advert.published_at else "—"
                ),
                "public_status": advert.public_status or "—",
                "url": f"https://cars.av.by/{advert.avby_id}",
            }
        )

    eu_listings = find_eu_matches(
        db,
        make=ys.target.make or ys.make or "",
        model=ys.target.model or ys.model_name or "",
        year=ys.year,
        max_price_usd=DEFAULT_MAX_PRICE_USD,
        max_hp=DEFAULT_MAX_HP,
    )

    return {
        "year_stat_id": ys.id,
        "target_id": ys.target.id,
        "make": ys.target.make,
        "model": ys.target.model,
        "generation": ys.target.generation or "—",
        "year": ys.year,
        "hp": hp,
        "catalog_slug": ys.target.catalog_slug,
        "row": row.as_dict() if row else None,
        "main_filter_url": ys.main_filter_url,
        "active_filter_url": ys.active_filter_url,
        "image_url": ys.image_url,
        "ocenka_url": (
            f"https://av.by/ocenka-avto/{ys.target.catalog_slug}_{ys.year}"
        ),
        "price_stats_url": f"/admin/price-stats/{ys.target.id}?year={ys.year}",
        "histogram": {"labels": hist_labels, "counts": hist_counts},
        "price_history": {"labels": hist_labels_line, "values": hist_values_line},
        "sold_table": sold_table,
        "eu_listings": eu_listings,
    }


def find_eu_matches(
    db: Session,
    *,
    make: str,
    model: str,
    year: int,
    max_price_usd: float,
    max_hp: int,
    limit: int = 30,
) -> list[dict[str, Any]]:
    make_s = (make or "").strip()
    model_s = (model or "").strip()
    if not make_s or not model_s:
        return []

    rates = fetch_nbrb_rates()
    query = (
        db.query(CarListing)
        .filter(CarListing.status == ListingStatus.published)
        .filter(CarListing.source.in_(_EU_SOURCES))
        .filter(CarListing.brand.ilike(make_s))
        .filter(CarListing.year == year)
        .filter(CarListing.price.isnot(None))
        .filter(CarListing.price_byn_missing.is_(False))
    )
    # Model match: allow substring either way for catalog vs listing naming.
    model_like = f"%{model_s}%"
    query = query.filter(CarListing.model.ilike(model_like))
    if max_hp:
        query = query.filter(
            (CarListing.engine_power_hp.is_(None))
            | (CarListing.engine_power_hp <= max_hp)
        )

    candidates = (
        query.order_by(CarListing.price.asc()).limit(200).all()
    )
    out: list[dict[str, Any]] = []
    for listing in candidates:
        price_byn = _num(listing.price)
        if price_byn is None:
            continue
        if rates:
            price_usd = rates.convert_byn_to_usd(price_byn)
        else:
            # Rough fallback if NBRB unavailable (~3.2 BYN/USD).
            price_usd = price_byn / 3.2
        if price_usd > max_price_usd:
            continue
        out.append(
            {
                "id": listing.id,
                "title": listing.title,
                "source": listing.source,
                "year": listing.year,
                "mileage": listing.mileage,
                "hp": listing.engine_power_hp,
                "price_byn": round(price_byn, 0),
                "price_usd": round(price_usd, 0),
                "price_usd_label": f"{price_usd:,.0f} $".replace(",", " "),
                "url": f"/listings/{listing.id}",
                "source_url": listing.source_url,
                "city": listing.city,
            }
        )
        if len(out) >= limit:
            break
    return out


def list_query_string(**params: Any) -> str:
    pairs: list[tuple[str, str]] = []
    for key, value in params.items():
        if value is None or value == "":
            continue
        pairs.append((key, str(value)))
    return urlencode(pairs)


def parse_filters(
    *,
    max_hp: int | None = None,
    max_price_usd: float | None = None,
    min_sold_n: int | None = None,
    max_median_days: float | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    make: str | None = None,
    q: str | None = None,
) -> ArbitrageFilters:
    return ArbitrageFilters(
        max_hp=int(max_hp) if max_hp else DEFAULT_MAX_HP,
        max_price_usd=float(max_price_usd) if max_price_usd else DEFAULT_MAX_PRICE_USD,
        min_sold_n=int(min_sold_n) if min_sold_n is not None else DEFAULT_MIN_SOLD_N,
        max_median_days=float(max_median_days) if max_median_days else None,
        year_from=year_from,
        year_to=year_to,
        make=(make or "").strip() or None,
        q=(q or "").strip() or None,
    )


def coverage_hint(db: Session) -> dict[str, Any]:
    sold_n = db.query(func.count(AvbyPriceSoldAdvert.id)).scalar() or 0
    year_ok = (
        db.query(func.count(AvbyPriceYearStat.id))
        .filter(AvbyPriceYearStat.fetch_status == "ok")
        .scalar()
        or 0
    )
    last_fetched = db.query(func.max(AvbyPriceYearStat.fetched_at)).scalar()
    return {
        "sold_adverts": int(sold_n),
        "year_ok": int(year_ok),
        "last_fetched_at": last_fetched,
        "last_fetched_label": (
            last_fetched.strftime("%d.%m.%Y %H:%M") if last_fetched else "—"
        ),
    }
