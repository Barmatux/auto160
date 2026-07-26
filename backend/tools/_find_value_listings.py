"""Find best-value listings: price below segment median with decent specs."""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import CarListing, ListingStatus


def main() -> int:
    db = SessionLocal()
    try:
        rows = (
            db.query(CarListing)
            .filter(
                CarListing.avby_id.isnot(None),
                CarListing.status == ListingStatus.published,
                CarListing.price > 0,
            )
            .all()
        )

        # Segment medians: brand + model + year
        seg_prices: dict[tuple[str, str, int], list[float]] = defaultdict(list)
        bm_prices: dict[tuple[str, str], list[float]] = defaultdict(list)
        for r in rows:
            if not r.brand or not r.model or not r.year:
                continue
            p = float(r.price)
            seg_prices[(r.brand, r.model, int(r.year))].append(p)
            bm_prices[(r.brand, r.model)].append(p)

        seg_median = {k: statistics.median(v) for k, v in seg_prices.items() if len(v) >= 3}
        bm_median = {k: statistics.median(v) for k, v in bm_prices.items() if len(v) >= 5}

        candidates = []
        for r in rows:
            if not r.brand or not r.model or not r.year:
                continue
            price = float(r.price)
            year = int(r.year)
            mileage = int(r.mileage or 0)
            hp = int(r.engine_power_hp or 0)

            # Skip junk / data errors
            if year < 2005:
                continue
            if mileage > 400_000:
                continue
            if price < 50_000:
                continue
            if hp > 160:
                continue

            key = (r.brand, r.model, year)
            ref = seg_median.get(key)
            ref_label = f"{r.brand} {r.model} {year}"
            peers = len(seg_prices.get(key, []))
            if ref is None:
                key2 = (r.brand, r.model)
                ref = bm_median.get(key2)
                ref_label = f"{r.brand} {r.model} (all years)"
                peers = len(bm_prices.get(key2, []))
            if ref is None or ref <= 0 or peers < 5:
                continue

            discount_pct = (ref - price) / ref * 100
            if discount_pct < 12:
                continue

            # Value score: discount weighted by recency and low mileage
            year_bonus = max(0, year - 2010) * 0.5
            mileage_penalty = min(mileage / 100_000, 3.0)
            score = discount_pct + year_bonus - mileage_penalty

            candidates.append(
                {
                    "id": r.id,
                    "avby_id": r.avby_id,
                    "title": r.title,
                    "brand": r.brand,
                    "model": r.model,
                    "year": year,
                    "price": round(price),
                    "mileage": mileage,
                    "hp": hp or None,
                    "city": r.city,
                    "engine_type": r.engine_type,
                    "transmission": r.transmission_type,
                    "body_type": r.body_type,
                    "source_url": r.source_url,
                    "segment_ref": ref_label,
                    "segment_median": round(ref),
                    "peers_in_segment": peers,
                    "discount_pct": round(discount_pct, 1),
                    "score": round(score, 1),
                    "price_per_year_km": round(price / max(mileage, 1), 1),
                }
            )

        candidates.sort(key=lambda x: (-x["score"], -x["discount_pct"]))

        # Diversify: max 2 per brand+model
        picked = []
        seen_bm: dict[tuple[str, str], int] = defaultdict(int)
        for c in candidates:
            bm = (c["brand"], c["model"])
            if seen_bm[bm] >= 2:
                continue
            seen_bm[bm] += 1
            picked.append(c)
            if len(picked) >= 20:
                break

        print(json.dumps({"count_scanned": len(rows), "candidates": len(candidates), "top": picked}, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
