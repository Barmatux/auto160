"""Curated value picks: newer, reasonable mileage, strong discount vs segment."""
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

        seg: dict[tuple[str, str, int], list[float]] = defaultdict(list)
        for r in rows:
            if r.brand and r.model and r.year:
                seg[(r.brand, r.model, int(r.year))].append(float(r.price))
        med = {k: statistics.median(v) for k, v in seg.items() if len(v) >= 4}

        picks = []
        for r in rows:
            if not r.brand or not r.model or not r.year:
                continue
            year = int(r.year)
            mileage = int(r.mileage or 0)
            hp = int(r.engine_power_hp or 0)
            price = float(r.price)
            key = (r.brand, r.model, year)
            ref = med.get(key)
            peers = len(seg.get(key, []))
            if not ref or peers < 4 or hp > 160:
                continue
            if year < 2012 or mileage > 250_000 or price < 100_000:
                continue
            disc = (ref - price) / ref * 100
            if disc < 18:
                continue
            # interesting = newer + lower mileage + meaningful discount
            score = disc + (year - 2012) * 1.2 - (mileage / 50_000)
            picks.append({
                "id": r.id,
                "avby_id": r.avby_id,
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
                "segment_median": round(ref),
                "peers": peers,
                "discount_pct": round(disc, 1),
                "score": round(score, 1),
            })

        picks.sort(key=lambda x: -x["score"])
        out = []
        seen = set()
        for p in picks:
            k = (p["brand"], p["model"])
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
            if len(out) >= 15:
                break

        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
