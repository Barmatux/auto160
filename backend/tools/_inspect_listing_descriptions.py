"""Inspect listing descriptions for damage signals."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import SessionLocal
from app.models import CarListing

IDS = [
    763, 1576, 6438, 335, 10392, 11113, 8020, 9872, 873, 470,
    1699, 5226, 719, 6693, 861, 1470, 754, 5477, 6884,
]

DAMAGE_PATTERNS = [
    r"дтп",
    r"бит(?!ый|ая|ое|ые|ым|ом|ую|ыми)?",  # handled separately below
    r"бит[аы]?й",
    r"битая",
    r"битое",
    r"битые",
    r"б/u",
    r"б\\u",
    r"варен",
    r"варё",
    r"окраш",
    r"краш",
    r"crash",
    r"accident",
    r"поврежд",
    r"после\s+удар",
    r"после\s+дтп",
    r"не\s+на\s+ходу",
    r"на\s+запчаст",
    r"требует\s+ремонт",
    r"нужен\s+ремонт",
    r"без\s+капот",
    r"без\s+бампер",
    r"не\s+заводит",
    r"утоп",
    r"под\s+восстан",
    r"с\s+дефект",
    r"дефект",
    r"аварий",
    r"кузовн",
    r"шпакл",
    r"перекрас",
    r"силов",
    r"подушк",
    r"airbag",
    r"totaled",
    r"salvage",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in DAMAGE_PATTERNS]


def damage_hits(text: str) -> list[str]:
    if not text:
        return []
    hits = []
    for pat in COMPILED:
        if pat.search(text):
            hits.append(pat.pattern)
    return hits


def main() -> int:
    db = SessionLocal()
    try:
        rows = db.query(CarListing).filter(CarListing.id.in_(IDS)).all()
        out = []
        for r in sorted(rows, key=lambda x: x.id):
            desc = (r.description or "").strip()
            hits = damage_hits(desc)
            out.append({
                "id": r.id,
                "avby_id": r.avby_id,
                "title": r.title,
                "price": float(r.price or 0),
                "damage_hits": hits,
                "flagged": bool(hits),
                "description_preview": desc[:500] if desc else "(empty)",
                "description_len": len(desc),
            })
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
