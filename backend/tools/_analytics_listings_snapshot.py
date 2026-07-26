"""One-off analytics snapshot for car_listings (run on VM or locally)."""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, text

from app.db import SessionLocal
from app.models import CarListing, ListingStatus


def pct(n: int, total: int) -> float:
    return round(100 * n / total, 1) if total else 0.0


def iqr_outliers(values: list[float]) -> dict:
    if len(values) < 4:
        return {"low": [], "high": [], "q1": None, "q3": None, "iqr": None}
    sorted_vals = sorted(values)
    q1 = statistics.quantiles(sorted_vals, n=4)[0]
    q3 = statistics.quantiles(sorted_vals, n=4)[2]
    iqr = q3 - q1
    low_fence = q1 - 1.5 * iqr
    high_fence = q3 + 1.5 * iqr
    low = [v for v in sorted_vals if v < low_fence]
    high = [v for v in sorted_vals if v > high_fence]
    return {
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        "iqr": round(iqr, 2),
        "low_fence": round(low_fence, 2),
        "high_fence": round(high_fence, 2),
        "low_count": len(low),
        "high_count": len(high),
        "low_min": round(min(low), 2) if low else None,
        "high_max": round(max(high), 2) if high else None,
    }


def main() -> int:
    db = SessionLocal()
    try:
        rows = (
            db.query(CarListing)
            .filter(CarListing.avby_id.isnot(None))
            .all()
        )
        total = len(rows)
        if not total:
            print(json.dumps({"error": "no avby listings"}, ensure_ascii=False))
            return 1

        published = sum(1 for r in rows if r.status == ListingStatus.published)
        archived = sum(1 for r in rows if r.status == ListingStatus.archived)

        prices = [float(r.price) for r in rows if r.price and float(r.price) > 0]
        mileages = [int(r.mileage) for r in rows if r.mileage is not None and r.mileage >= 0]
        years = [int(r.year) for r in rows if r.year]
        hp_vals = [int(r.engine_power_hp) for r in rows if r.engine_power_hp]

        brand_counts = Counter(r.brand for r in rows if r.brand)
        model_counts = Counter(f"{r.brand} {r.model}" for r in rows if r.brand and r.model)
        city_counts = Counter(r.city for r in rows if r.city)
        body_counts = Counter(r.body_type for r in rows if r.body_type)
        engine_counts = Counter(r.engine_type for r in rows if r.engine_type)
        trans_counts = Counter(r.transmission_type for r in rows if r.transmission_type)
        drive_counts = Counter(r.drive_type for r in rows if r.drive_type)

        with_vin = sum(1 for r in rows if r.vin)
        with_catalog = sum(1 for r in rows if r.catalog_item_id)
        vin_indicated_true = sum(1 for r in rows if r.vin_indicated is True)
        vin_indicated_false = sum(1 for r in rows if r.vin_indicated is False)

        # price per year bucket
        year_price: dict[int, list[float]] = defaultdict(list)
        for r in rows:
            if r.year and r.price and float(r.price) > 0:
                year_price[int(r.year)].append(float(r.price))

        year_medians = {
            str(y): round(statistics.median(vals), 0)
            for y, vals in sorted(year_price.items())
        }

        # monthly import trend by created_at
        month_counts = Counter()
        for r in rows:
            if r.created_at:
                month_counts[r.created_at.strftime("%Y-%m")] += 1

        # price bands USD (stored as price - check if USD)
        bands = {"<10k": 0, "10-15k": 0, "15-20k": 0, "20-30k": 0, "30-50k": 0, ">50k": 0}
        for p in prices:
            if p < 10000:
                bands["<10k"] += 1
            elif p < 15000:
                bands["10-15k"] += 1
            elif p < 20000:
                bands["15-20k"] += 1
            elif p < 30000:
                bands["20-30k"] += 1
            elif p < 50000:
                bands["30-50k"] += 1
            else:
                bands[">50k"] += 1

        mileage_bands = {"0-30k": 0, "30-60k": 0, "60-100k": 0, "100-150k": 0, ">150k": 0}
        for m in mileages:
            if m <= 30000:
                mileage_bands["0-30k"] += 1
            elif m <= 60000:
                mileage_bands["30-60k"] += 1
            elif m <= 100000:
                mileage_bands["60-100k"] += 1
            elif m <= 150000:
                mileage_bands["100-150k"] += 1
            else:
                mileage_bands[">150k"] += 1

        hp_bands = {"<=100": 0, "101-130": 0, "131-160": 0, ">160": 0}
        for h in hp_vals:
            if h <= 100:
                hp_bands["<=100"] += 1
            elif h <= 130:
                hp_bands["101-130"] += 1
            elif h <= 160:
                hp_bands["131-160"] += 1
            else:
                hp_bands[">160"] += 1

        # top expensive / cheap outliers
        sorted_by_price = sorted(rows, key=lambda r: float(r.price or 0), reverse=True)
        top_expensive = [
            {
                "id": r.id,
                "avby_id": r.avby_id,
                "title": r.title[:80],
                "brand": r.brand,
                "model": r.model,
                "year": r.year,
                "price": float(r.price),
                "mileage": r.mileage,
                "hp": r.engine_power_hp,
            }
            for r in sorted_by_price[:8]
        ]
        top_cheap = [
            {
                "id": r.id,
                "avby_id": r.avby_id,
                "title": r.title[:80],
                "brand": r.brand,
                "model": r.model,
                "year": r.year,
                "price": float(r.price),
                "mileage": r.mileage,
                "hp": r.engine_power_hp,
            }
            for r in sorted(rows, key=lambda r: float(r.price or 0))[:8]
        ]

        # suspicious: very low price for year, very high mileage low price
        suspicious = []
        for r in rows:
            p = float(r.price or 0)
            if not p:
                continue
            y = int(r.year or 0)
            m = int(r.mileage or 0)
            if y >= 2018 and p < 8000:
                suspicious.append({"type": "low_price_new", "id": r.id, "year": y, "price": p, "brand": r.brand, "model": r.model})
            if m > 200000 and p < 12000:
                suspicious.append({"type": "high_mileage_cheap", "id": r.id, "mileage": m, "price": p, "brand": r.brand, "model": r.model})
            if r.engine_power_hp and r.engine_power_hp > 160:
                suspicious.append({"type": "over_hp_filter", "id": r.id, "hp": r.engine_power_hp, "brand": r.brand, "model": r.model})

        # sync runs summary
        sync_stats = db.execute(
            text(
                """
                SELECT status, COUNT(*) AS cnt,
                       SUM(created_count) AS created,
                       SUM(updated_count) AS updated
                FROM avby_sync_runs
                GROUP BY status
                ORDER BY status
                """
            )
        ).mappings().all()

        recent_syncs = db.execute(
            text(
                """
                SELECT id, started_at, finished_at, status, created_count, updated_count, pages_fetched_count, error_message
                FROM avby_sync_runs
                ORDER BY id DESC
                LIMIT 10
                """
            )
        ).mappings().all()

        snapshot = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "totals": {
                "listings_avby": total,
                "published": published,
                "archived": archived,
                "published_pct": pct(published, total),
            },
            "coverage": {
                "with_vin": with_vin,
                "with_vin_pct": pct(with_vin, total),
                "vin_indicated_true": vin_indicated_true,
                "vin_indicated_false": vin_indicated_false,
                "with_catalog_link": with_catalog,
                "with_catalog_pct": pct(with_catalog, total),
            },
            "price_usd": {
                "count": len(prices),
                "min": round(min(prices), 0) if prices else None,
                "max": round(max(prices), 0) if prices else None,
                "mean": round(statistics.mean(prices), 0) if prices else None,
                "median": round(statistics.median(prices), 0) if prices else None,
                "stdev": round(statistics.stdev(prices), 0) if len(prices) > 1 else None,
                "bands": bands,
                "outliers_iqr": iqr_outliers(prices),
            },
            "mileage_km": {
                "count": len(mileages),
                "min": min(mileages) if mileages else None,
                "max": max(mileages) if mileages else None,
                "mean": round(statistics.mean(mileages), 0) if mileages else None,
                "median": round(statistics.median(mileages), 0) if mileages else None,
                "bands": mileage_bands,
                "outliers_iqr": iqr_outliers([float(m) for m in mileages]),
            },
            "year": {
                "min": min(years) if years else None,
                "max": max(years) if years else None,
                "median": round(statistics.median(years), 0) if years else None,
                "distribution": dict(Counter(years).most_common()),
                "median_price_by_year": year_medians,
            },
            "engine_power_hp": {
                "count": len(hp_vals),
                "min": min(hp_vals) if hp_vals else None,
                "max": max(hp_vals) if hp_vals else None,
                "mean": round(statistics.mean(hp_vals), 1) if hp_vals else None,
                "median": round(statistics.median(hp_vals), 0) if hp_vals else None,
                "bands": hp_bands,
                "outliers_iqr": iqr_outliers([float(h) for h in hp_vals]),
            },
            "top_brands": brand_counts.most_common(15),
            "top_models": model_counts.most_common(15),
            "top_cities": city_counts.most_common(12),
            "body_types": body_counts.most_common(10),
            "engine_types": engine_counts.most_common(8),
            "transmissions": trans_counts.most_common(8),
            "drive_types": drive_counts.most_common(8),
            "import_by_month": dict(sorted(month_counts.items())),
            "top_expensive": top_expensive,
            "top_cheap": top_cheap,
            "suspicious_count": len(suspicious),
            "suspicious_sample": suspicious[:20],
            "sync_runs_by_status": [dict(r) for r in sync_stats],
            "recent_syncs": [
                {
                    **dict(r),
                    "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                    "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
                    "error_message": (r["error_message"] or "")[:120] or None,
                }
                for r in recent_syncs
            ],
        }
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
