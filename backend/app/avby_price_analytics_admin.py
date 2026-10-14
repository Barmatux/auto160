"""Admin views for av.by ocenka / price-statistics snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.listing_display import format_money_amount
from app.models import AvbyPriceHistoryPoint, AvbyPriceSoldAdvert, AvbyPriceStatTarget, AvbyPriceYearStat

RESOLVE_STATUS_LABELS = {
    "pending": "Ожидает",
    "ready": "Готово",
    "error": "Ошибка",
}
FETCH_STATUS_LABELS = {
    "ok": "OK",
    "error": "Ошибка",
}


def _num(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _usd(value: Any) -> str:
    amount = _num(value)
    if amount is None:
        return "—"
    return f"{format_money_amount(amount)} $"


def _byn(value: Any) -> str:
    amount = _num(value)
    if amount is None:
        return "—"
    return f"{format_money_amount(amount)} BYN"


def _planned_years(target: AvbyPriceStatTarget) -> int:
    y0 = target.year_from
    y1 = target.year_to or target.year_from
    if y0 and y1 and y1 >= y0:
        return int(y1) - int(y0) + 1
    if y0:
        return 1
    return 0


@dataclass(frozen=True)
class PriceStatsSummary:
    targets_total: int
    targets_ready: int
    targets_pending: int
    targets_error: int
    year_ok: int
    year_error: int
    years_planned: int
    history_points: int
    sold_adverts: int
    last_fetched_at: datetime | None
    coverage_pct: float

    @property
    def coverage_label(self) -> str:
        return f"{self.coverage_pct:.0f}%"

    @property
    def last_fetched_label(self) -> str:
        if not self.last_fetched_at:
            return "—"
        return self.last_fetched_at.strftime("%d.%m.%Y %H:%M")


def build_price_stats_summary(db: Session) -> PriceStatsSummary:
    targets_total = db.query(func.count(AvbyPriceStatTarget.id)).scalar() or 0
    targets_ready = (
        db.query(func.count(AvbyPriceStatTarget.id))
        .filter(AvbyPriceStatTarget.resolve_status == "ready")
        .scalar()
        or 0
    )
    targets_pending = (
        db.query(func.count(AvbyPriceStatTarget.id))
        .filter(AvbyPriceStatTarget.resolve_status == "pending")
        .scalar()
        or 0
    )
    targets_error = (
        db.query(func.count(AvbyPriceStatTarget.id))
        .filter(AvbyPriceStatTarget.resolve_status == "error")
        .scalar()
        or 0
    )
    year_ok = (
        db.query(func.count(AvbyPriceYearStat.id))
        .filter(AvbyPriceYearStat.fetch_status == "ok")
        .scalar()
        or 0
    )
    year_error = (
        db.query(func.count(AvbyPriceYearStat.id))
        .filter(AvbyPriceYearStat.fetch_status == "error")
        .scalar()
        or 0
    )
    history_points = db.query(func.count(AvbyPriceHistoryPoint.id)).scalar() or 0
    sold_adverts = db.query(func.count(AvbyPriceSoldAdvert.id)).scalar() or 0
    last_fetched_at = db.query(func.max(AvbyPriceYearStat.fetched_at)).scalar()

    years_planned = 0
    for target in db.query(AvbyPriceStatTarget).all():
        years_planned += _planned_years(target)
    coverage_pct = (100.0 * year_ok / years_planned) if years_planned else 0.0

    return PriceStatsSummary(
        targets_total=int(targets_total),
        targets_ready=int(targets_ready),
        targets_pending=int(targets_pending),
        targets_error=int(targets_error),
        year_ok=int(year_ok),
        year_error=int(year_error),
        years_planned=int(years_planned),
        history_points=int(history_points),
        sold_adverts=int(sold_adverts),
        last_fetched_at=last_fetched_at,
        coverage_pct=coverage_pct,
    )


def list_makes(db: Session) -> list[str]:
    rows = (
        db.query(AvbyPriceStatTarget.make)
        .distinct()
        .order_by(AvbyPriceStatTarget.make.asc())
        .all()
    )
    return [str(row[0]) for row in rows if row[0]]


def list_price_stat_targets(
    db: Session,
    *,
    q: str | None = None,
    make: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    query = db.query(AvbyPriceStatTarget)
    if make:
        query = query.filter(AvbyPriceStatTarget.make == make)
    if status in RESOLVE_STATUS_LABELS:
        query = query.filter(AvbyPriceStatTarget.resolve_status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            (AvbyPriceStatTarget.make.ilike(like))
            | (AvbyPriceStatTarget.model.ilike(like))
            | (AvbyPriceStatTarget.generation.ilike(like))
            | (AvbyPriceStatTarget.catalog_slug.ilike(like))
        )

    total = query.count()
    targets = (
        query.order_by(
            AvbyPriceStatTarget.make.asc(),
            AvbyPriceStatTarget.model.asc(),
            AvbyPriceStatTarget.catalog_slug.asc(),
        )
        .offset(max(page - 1, 0) * per_page)
        .limit(per_page)
        .all()
    )
    if not targets:
        return [], total

    target_ids = [t.id for t in targets]
    year_rows = (
        db.query(AvbyPriceYearStat)
        .filter(AvbyPriceYearStat.target_id.in_(target_ids))
        .order_by(AvbyPriceYearStat.year.asc())
        .all()
    )
    by_target: dict[int, list[AvbyPriceYearStat]] = {tid: [] for tid in target_ids}
    for row in year_rows:
        by_target.setdefault(row.target_id, []).append(row)

    result: list[dict[str, Any]] = []
    for target in targets:
        stats = by_target.get(target.id) or []
        ok_stats = [s for s in stats if s.fetch_status == "ok"]
        planned = _planned_years(target)
        priced = [s for s in ok_stats if _num(s.price_usd) and _num(s.price_usd) > 0]
        median_sample = None
        if priced:
            mid = priced[len(priced) // 2]
            median_sample = mid
        latest = max(ok_stats, key=lambda s: s.fetched_at) if ok_stats else None
        result.append(
            {
                "id": target.id,
                "make": target.make,
                "model": target.model,
                "generation": target.generation or "—",
                "years_label": (
                    f"{target.year_from}–{target.year_to}"
                    if target.year_from and target.year_to
                    else (str(target.year_from) if target.year_from else "—")
                ),
                "catalog_slug": target.catalog_slug,
                "resolve_status": target.resolve_status,
                "resolve_status_label": RESOLVE_STATUS_LABELS.get(
                    target.resolve_status, target.resolve_status
                ),
                "years_ok": len(ok_stats),
                "years_planned": planned,
                "coverage_label": (
                    f"{len(ok_stats)}/{planned}" if planned else str(len(ok_stats))
                ),
                "sample_price_usd": _usd(median_sample.price_usd) if median_sample else "—",
                "sample_year": median_sample.year if median_sample else None,
                "adverts_sum": sum(int(s.advert_count or 0) for s in ok_stats),
                "last_fetched_at": latest.fetched_at if latest else None,
                "source_url": target.source_url,
                "detail_url": f"/admin/price-stats/{target.id}",
            }
        )
    return result, total


def build_target_detail(db: Session, target_id: int) -> dict[str, Any] | None:
    target = (
        db.query(AvbyPriceStatTarget)
        .options(
            joinedload(AvbyPriceStatTarget.year_stats)
            .joinedload(AvbyPriceYearStat.history_points),
            joinedload(AvbyPriceStatTarget.year_stats)
            .joinedload(AvbyPriceYearStat.sold_adverts),
        )
        .filter(AvbyPriceStatTarget.id == target_id)
        .first()
    )
    if target is None:
        return None

    year_rows = sorted(target.year_stats, key=lambda s: s.year)
    years: list[dict[str, Any]] = []
    history_chart: list[dict[str, Any]] = []
    sold_rows: list[dict[str, Any]] = []

    for row in year_rows:
        years.append(
            {
                "id": row.id,
                "year": row.year,
                "price_usd": _usd(row.price_usd),
                "price_byn": _byn(row.price_byn),
                "min_price_usd": _usd(row.min_price_usd),
                "max_price_usd": _usd(row.max_price_usd),
                "advert_count": row.advert_count if row.advert_count is not None else "—",
                "active_advert_count": (
                    row.active_advert_count if row.active_advert_count is not None else "—"
                ),
                "activity_new_60d": row.activity_new_60d if row.activity_new_60d is not None else "—",
                "activity_removed_60d": (
                    row.activity_removed_60d if row.activity_removed_60d is not None else "—"
                ),
                "fetch_status": row.fetch_status,
                "fetch_status_label": FETCH_STATUS_LABELS.get(row.fetch_status, row.fetch_status),
                "fetched_at": row.fetched_at,
                "main_filter_url": row.main_filter_url,
                "image_url": row.image_url,
            }
        )
        for point in sorted(row.history_points, key=lambda p: (p.year, p.month)):
            amount = _num(point.median_price_usd)
            if amount is None:
                continue
            history_chart.append(
                {
                    "label": f"{point.month:02d}.{point.year}",
                    "year": point.year,
                    "month": point.month,
                    "value": amount,
                    "value_label": _usd(amount),
                    "source_year": row.year,
                }
            )
        for advert in sorted(
            row.sold_adverts,
            key=lambda a: a.published_at or datetime.min,
            reverse=True,
        ):
            sold_rows.append(
                {
                    "avby_id": advert.avby_id,
                    "year": row.year,
                    "price_usd": _usd(advert.price_usd),
                    "price_byn": _byn(advert.price_byn),
                    "days_on_sale": advert.days_on_sale if advert.days_on_sale is not None else "—",
                    "published_at": advert.published_at,
                    "public_status": advert.public_status or "—",
                    "url": f"https://cars.av.by/{advert.avby_id}",
                }
            )

    # Prefer history from the middle priced year for the sparkline; else merge unique months.
    chart_points = _dedupe_history_chart(history_chart)
    chart_svg = _history_svg(chart_points)

    return {
        "target": target,
        "title": f"{target.make} {target.model}"
        + (f" · {target.generation}" if target.generation else ""),
        "years_label": (
            f"{target.year_from}–{target.year_to}"
            if target.year_from and target.year_to
            else (str(target.year_from) if target.year_from else "—")
        ),
        "resolve_status_label": RESOLVE_STATUS_LABELS.get(
            target.resolve_status, target.resolve_status
        ),
        "years": years,
        "years_ok": sum(1 for y in years if y["fetch_status"] == "ok"),
        "sold_rows": sold_rows[:40],
        "sold_total": len(sold_rows),
        "history_points": chart_points,
        "history_svg": chart_svg,
        "ocenka_url": (
            f"https://av.by/ocenka-avto/{target.catalog_slug}_{target.year_from}"
            if target.year_from
            else f"https://av.by/ocenka-avto/{target.catalog_slug}"
        ),
    }


def _dedupe_history_chart(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one median per calendar month (prefer non-zero, later source year)."""
    best: dict[tuple[int, int], dict[str, Any]] = {}
    for point in points:
        key = (int(point["year"]), int(point["month"]))
        prev = best.get(key)
        if prev is None:
            best[key] = point
            continue
        if prev["value"] <= 0 and point["value"] > 0:
            best[key] = point
            continue
        if point["source_year"] >= prev["source_year"] and point["value"] > 0:
            best[key] = point
    return [best[k] for k in sorted(best.keys())]


def _history_svg(points: list[dict[str, Any]], *, width: int = 640, height: int = 160) -> str | None:
    values = [p["value"] for p in points if p["value"] is not None]
    if len(values) < 2:
        return None
    lo = min(values)
    hi = max(values)
    span = (hi - lo) or 1.0
    pad_x = 12.0
    pad_y = 14.0
    usable_w = width - 2 * pad_x
    usable_h = height - 2 * pad_y
    coords: list[str] = []
    for idx, point in enumerate(points):
        x = pad_x + (usable_w * idx / (len(points) - 1))
        y = pad_y + usable_h * (1 - (point["value"] - lo) / span)
        coords.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(coords)
    first_label = points[0]["label"]
    last_label = points[-1]["label"]
    return (
        f'<svg class="price-stats-chart" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="История медианной цены USD">'
        f'<polyline fill="none" stroke="currentColor" stroke-width="2" points="{polyline}" />'
        f'<text x="{pad_x}" y="{height - 2}" font-size="11">{first_label}</text>'
        f'<text x="{width - pad_x}" y="{height - 2}" font-size="11" text-anchor="end">{last_label}</text>'
        f'<text x="{pad_x}" y="12" font-size="11">{format_money_amount(hi)} $</text>'
        f'<text x="{pad_x}" y="{height - 18}" font-size="11">{format_money_amount(lo)} $</text>'
        f"</svg>"
    )


def list_query_string(
    *,
    q: str | None = None,
    make: str | None = None,
    status: str | None = None,
    page: int | None = None,
) -> str:
    params: dict[str, str | int] = {}
    if q:
        params["q"] = q
    if make:
        params["make"] = make
    if status:
        params["status"] = status
    if page and page > 1:
        params["page"] = page
    return urlencode(params)
