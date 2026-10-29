"""Admin views for av.by ocenka / price-statistics snapshots."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.listing_display import format_money_amount
from app.models import (
    AvbyPriceConfigStat,
    AvbyPriceHistoryPoint,
    AvbyPriceSoldAdvert,
    AvbyPriceStatTarget,
    AvbyPriceYearStat,
)

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


_MONTH_SHORT_RU = (
    "",
    "янв",
    "фев",
    "мар",
    "апр",
    "май",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
)


def build_target_detail(
    db: Session,
    target_id: int,
    *,
    selected_year: int | None = None,
) -> dict[str, Any] | None:
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
    year_activity: dict[int, list[dict[str, Any]]] = {}

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
                "is_selected": False,
            }
        )
        activity_points = _parse_activity_by_month(row.activity_by_month)
        if activity_points:
            year_activity[row.year] = activity_points
        for point in sorted(row.history_points, key=lambda p: (p.year, p.month)):
            amount = _num(point.median_price_usd)
            if amount is None:
                continue
            history_chart.append(
                {
                    "label": f"{point.month:02d}.{point.year}",
                    "short_label": _month_label(point.year, point.month),
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

    chart_points = _dedupe_history_chart(history_chart)
    chart_svg = _history_svg(chart_points)

    activity_years = sorted(year_activity.keys())
    chosen_year = _pick_activity_year(year_rows, activity_years, selected_year)
    if chosen_year is None and selected_year and any(r.year == selected_year for r in year_rows):
        chosen_year = selected_year
    elif chosen_year is None and year_rows:
        chosen_year = max(r.year for r in year_rows)
    for item in years:
        item["is_selected"] = item["year"] == chosen_year
    selected_row = next((r for r in year_rows if r.year == chosen_year), None)
    activity_months = year_activity.get(chosen_year, []) if chosen_year else []
    activity_chart = _activity_bars(activity_months)

    activity_summary = {
        "year": chosen_year,
        "new_60d": selected_row.activity_new_60d if selected_row else None,
        "removed_60d": selected_row.activity_removed_60d if selected_row else None,
        "activity_days": selected_row.activity_days if selected_row else None,
        "months": activity_months,
        "has_data": bool(activity_months),
        "year_links": [
            {
                "year": y,
                "url": f"/admin/price-stats/{target.id}?year={y}",
                "active": y == chosen_year,
            }
            for y in activity_years
        ],
    }

    config_rows: list[dict[str, Any]] = []
    if selected_row is not None:
        configs = (
            db.query(AvbyPriceConfigStat)
            .filter(AvbyPriceConfigStat.year_stat_id == selected_row.id)
            .order_by(
                AvbyPriceConfigStat.engine_type_label.asc(),
                AvbyPriceConfigStat.engine_capacity_id.asc(),
                AvbyPriceConfigStat.transmission_type_label.asc(),
                AvbyPriceConfigStat.drive_type_label.asc(),
            )
            .all()
        )
        for cfg in configs:
            config_rows.append(
                {
                    "engine_type": cfg.engine_type_label or cfg.engine_type_id,
                    "engine_capacity": cfg.engine_capacity_label or cfg.engine_capacity_id,
                    "transmission": cfg.transmission_type_label or cfg.transmission_type_id,
                    "drive": cfg.drive_type_label or cfg.drive_type_id,
                    "price_usd": _usd(cfg.price_usd),
                    "price_byn": _byn(cfg.price_byn),
                    "min_price_usd": _usd(cfg.min_price_usd),
                    "max_price_usd": _usd(cfg.max_price_usd),
                    "advert_count": cfg.advert_count if cfg.advert_count is not None else "—",
                    "fetch_status": cfg.fetch_status,
                    "fetch_status_label": FETCH_STATUS_LABELS.get(cfg.fetch_status, cfg.fetch_status),
                    "fetched_at": cfg.fetched_at,
                }
            )

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
        "activity": activity_summary,
        "activity_chart": activity_chart,
        "selected_year": chosen_year,
        "config_rows": config_rows,
        "config_year": chosen_year,
        "ocenka_url": (
            f"https://av.by/ocenka-avto/{target.catalog_slug}_{chosen_year or target.year_from}"
            if (chosen_year or target.year_from)
            else f"https://av.by/ocenka-avto/{target.catalog_slug}"
        ),
    }


def _month_label(year: int, month: int) -> str:
    name = _MONTH_SHORT_RU[month] if 1 <= month <= 12 else f"{month:02d}"
    return f"{name} {year % 100:02d}"


def _parse_activity_by_month(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        date_text = str(item.get("date") or "")
        year = month = None
        if len(date_text) >= 7 and date_text[4] == "-":
            try:
                year = int(date_text[0:4])
                month = int(date_text[5:7])
            except ValueError:
                year = month = None
        if year is None:
            year = int(item["year"]) if item.get("year") is not None else None
            month = int(item["month"]) if item.get("month") is not None else None
        if not year or not month:
            continue
        new_count = int(item.get("new") or 0)
        removed_count = int(item.get("removed") or 0)
        rows.append(
            {
                "year": year,
                "month": month,
                "date": date_text or f"{year:04d}-{month:02d}-01",
                "label": _month_label(year, month),
                "new": new_count,
                "removed": removed_count,
                "new_label": str(new_count),
                "removed_label": str(removed_count),
            }
        )
    rows.sort(key=lambda r: (r["year"], r["month"]))
    return rows


def _pick_activity_year(
    year_rows: list[AvbyPriceYearStat],
    activity_years: list[int],
    selected_year: int | None,
) -> int | None:
    if selected_year and selected_year in activity_years:
        return selected_year
    if not activity_years:
        return None
    best = None
    best_score = -1
    for row in year_rows:
        if row.year not in activity_years:
            continue
        score = int(row.advert_count or 0) + int(row.activity_removed_60d or 0) * 2
        if score > best_score:
            best_score = score
            best = row.year
    return best if best is not None else activity_years[len(activity_years) // 2]


def _activity_bars(months: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not months:
        return None
    peak = max(max(m["new"], m["removed"]) for m in months) or 1
    bars = []
    for item in months:
        bars.append(
            {
                **item,
                "new_pct": round(100.0 * item["new"] / peak, 1),
                "removed_pct": round(100.0 * item["removed"] / peak, 1),
            }
        )
    return {
        "bars": bars,
        "peak": peak,
        "total_new": sum(m["new"] for m in months),
        "total_removed": sum(m["removed"] for m in months),
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


def _nice_ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    if hi <= lo:
        return [float(lo)]
    raw = (hi - lo) / max(count - 1, 1)
    exp = math.floor(math.log10(raw)) if raw > 0 else 0
    base = 10 ** exp
    fraction = raw / base
    if fraction <= 1:
        nice = 1
    elif fraction <= 2:
        nice = 2
    elif fraction <= 5:
        nice = 5
    else:
        nice = 10
    step = nice * base
    start = math.floor(lo / step) * step
    ticks: list[float] = []
    value = start
    guard = 0
    while value <= hi + step * 0.001 and guard < 20:
        if value >= lo - step * 0.001:
            ticks.append(float(value))
        value += step
        guard += 1
    return ticks or [float(lo), float(hi)]


def _escape_svg_text(value: str) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _history_svg(points: list[dict[str, Any]], *, width: int = 760, height: int = 300) -> str | None:
    values = [p["value"] for p in points if p.get("value") is not None]
    if len(values) < 2:
        return None

    lo = min(values)
    hi = max(values)
    # Add headroom so the line isn't glued to edges / tooltips.
    pad_value = (hi - lo) * 0.08 if hi > lo else max(hi * 0.05, 100)
    y_min = max(0.0, lo - pad_value)
    y_max = hi + pad_value
    span = (y_max - y_min) or 1.0

    left = 64.0
    right = 24.0
    top = 36.0
    bottom = 46.0
    usable_w = width - left - right
    usable_h = height - top - bottom

    def x_at(idx: int) -> float:
        if len(points) == 1:
            return left + usable_w / 2
        return left + usable_w * idx / (len(points) - 1)

    def y_at(value: float) -> float:
        return top + usable_h * (1 - (value - y_min) / span)

    coords = [(x_at(i), y_at(p["value"])) for i, p in enumerate(points)]
    line_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    area_points = (
        f"{coords[0][0]:.1f},{top + usable_h:.1f} "
        + line_points
        + f" {coords[-1][0]:.1f},{top + usable_h:.1f}"
    )

    ticks = _nice_ticks(y_min, y_max, count=5)
    grid_parts: list[str] = []
    for tick in ticks:
        y = y_at(tick)
        grid_parts.append(
            f'<line class="price-stats-grid" x1="{left}" y1="{y:.1f}" '
            f'x2="{width - right}" y2="{y:.1f}" />'
            f'<text class="price-stats-axis" x="{left - 8}" y="{y + 4:.1f}" '
            f'text-anchor="end">{_escape_svg_text(format_money_amount(tick))}</text>'
        )

    label_step = max(1, len(points) // 8)
    label_parts: list[str] = []
    for idx, point in enumerate(points):
        if idx % label_step != 0 and idx != len(points) - 1:
            continue
        x = coords[idx][0]
        label_parts.append(
            f'<text class="price-stats-axis" x="{x:.1f}" y="{height - 14}" '
            f'text-anchor="middle">'
            f'{_escape_svg_text(point.get("short_label") or point["label"])}</text>'
        )

    tip_w = 118.0
    tip_h = 42.0
    dot_parts: list[str] = []
    for idx, ((x, y), point) in enumerate(zip(coords, points)):
        month = _escape_svg_text(point.get("short_label") or point["label"])
        value_label = _escape_svg_text(point["value_label"])
        # Keep tooltip inside the plot horizontally.
        tip_x = min(max(x - tip_w / 2, left + 4), width - right - tip_w - 4)
        tip_above = y - tip_h - 14 >= 4
        tip_y = y - tip_h - 14 if tip_above else y + 14
        tip_anchor_x = x - tip_x
        if tip_above:
            arrow = (
                f'<polygon class="price-stats-tip-bg" '
                f'points="{tip_anchor_x - 6:.1f},{tip_h:.0f} '
                f'{tip_anchor_x:.1f},{tip_h + 7:.0f} '
                f'{tip_anchor_x + 6:.1f},{tip_h:.0f}" />'
            )
        else:
            arrow = (
                f'<polygon class="price-stats-tip-bg" '
                f'points="{tip_anchor_x - 6:.1f},0 '
                f'{tip_anchor_x:.1f},-7 '
                f'{tip_anchor_x + 6:.1f},0" />'
            )
        dot_parts.append(
            f'<g class="price-stats-point" tabindex="0" role="button" '
            f'data-point-index="{idx}" aria-label="{month}: {value_label}">'
            f'<circle class="price-stats-hit" cx="{x:.1f}" cy="{y:.1f}" r="16" />'
            f'<circle class="price-stats-dot" cx="{x:.1f}" cy="{y:.1f}" r="4.5" />'
            f'<g class="price-stats-tip" transform="translate({tip_x:.1f},{tip_y:.1f})">'
            f'<rect class="price-stats-tip-bg" width="{tip_w:.0f}" height="{tip_h:.0f}" rx="8" />'
            f"{arrow}"
            f'<text class="price-stats-tip-month" x="10" y="17">{month}</text>'
            f'<text class="price-stats-tip-value" x="10" y="34">{value_label}</text>'
            f"</g></g>"
        )

    return (
        f'<svg class="price-stats-chart" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="История медианной цены USD">'
        f'<rect class="price-stats-plot" x="{left}" y="{top}" '
        f'width="{usable_w}" height="{usable_h}" rx="8" />'
        + "".join(grid_parts)
        + f'<polygon class="price-stats-area" points="{area_points}" />'
        + f'<polyline class="price-stats-line" fill="none" stroke-width="2.5" '
        f'points="{line_points}" />'
        + "".join(label_parts)
        + f'<text class="price-stats-axis price-stats-axis-title" x="12" y="16">USD</text>'
        + "".join(dot_parts)
        + "</svg>"
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
