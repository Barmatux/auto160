"""Find value listings excluding damaged cars (description-aware)."""
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
from app.listing_description_quality import describe_damage_flags, is_damaged_listing
from app.models import CarListing, ListingStatus

# Soft quality warnings (not auto-exclude)
_WARN_ENGINE = ("подтраивает", "подтраевает", "стучит", "течет", "течёт", "копит", "дымит", "глохнет")


def engine_warning(text: str | None) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(w in lower for w in _WARN_ENGINE)


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
        clean_rows = []
        excluded_damage = 0
        for r in rows:
            if is_damaged_listing(r.description) or engine_warning(r.description):
                excluded_damage += 1
                continue
            clean_rows.append(r)
            if r.brand and r.model and r.year:
                seg[(r.brand, r.model, int(r.year))].append(float(r.price))

        med = {k: statistics.median(v) for k, v in seg.items() if len(v) >= 4}

        picks = []
        for r in clean_rows:
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
            if disc < 15:
                continue

            body = (r.description or "")[:300]
            score = disc + (year - 2012) * 1.0 - (mileage / 60_000)
            if engine_warning(r.description):
                score -= 8

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
                "engine_warning": engine_warning(r.description),
                "description_preview": body.replace("\n", " ").strip(),
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
            if len(out) >= 12:
                break

        print(json.dumps({
            "scanned": len(rows),
            "excluded_damaged": excluded_damage,
            "clean_pool": len(clean_rows),
            "top": out,
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
