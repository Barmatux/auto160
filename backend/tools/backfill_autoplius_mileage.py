#!/usr/bin/env python3
"""Backfill Autoplius listing mileage from a JSON map of listing_id -> km.

Example:

  python tools/backfill_autoplius_mileage.py --from-json /tmp/mileage.json --dry-run
  python tools/backfill_autoplius_mileage.py --from-json /tmp/mileage.json

JSON formats accepted:
  {"21208": 74000, "21206": null}
  [{"id": 21208, "mileage": 74000}, ...]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.models import CarListing


def _load_updates(path: Path) -> dict[int, int]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, int] = {}
    if isinstance(raw, dict):
        items = raw.items()
        for key, value in items:
            if value is None:
                continue
            try:
                lid = int(key)
                km = int(value)
            except (TypeError, ValueError):
                continue
            if 0 <= km <= 900_000:
                out[lid] = km
        return out
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                lid = int(item.get("id"))
                km = item.get("mileage", item.get("mileage_km"))
                if km is None:
                    continue
                km_i = int(km)
            except (TypeError, ValueError):
                continue
            if 0 <= km_i <= 900_000:
                out[lid] = km_i
        return out
    raise SystemExit(f"Unsupported JSON shape in {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Autoplius mileages from JSON")
    parser.add_argument("--from-json", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-zero", action="store_true", default=True)
    parser.add_argument("--allow-overwrite", action="store_true")
    args = parser.parse_args()

    updates = _load_updates(args.from_json)
    print(f"loaded={len(updates)} from {args.from_json}")

    db = SessionLocal()
    changed = skipped = missing = 0
    try:
        for lid, km in sorted(updates.items()):
            listing = db.get(CarListing, lid)
            if listing is None:
                missing += 1
                continue
            if listing.source != "autoplius":
                skipped += 1
                continue
            if not args.allow_overwrite and listing.mileage and listing.mileage > 0:
                skipped += 1
                continue
            if args.only_zero and not args.allow_overwrite and listing.mileage not in (None, 0):
                skipped += 1
                continue
            old = listing.mileage
            if old == km:
                skipped += 1
                continue
            print(f"{lid}: {old} -> {km}")
            if not args.dry_run:
                listing.mileage = km
            changed += 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    print(f"done dry_run={args.dry_run} changed={changed} skipped={skipped} missing={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
