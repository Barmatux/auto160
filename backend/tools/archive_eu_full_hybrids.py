#!/usr/bin/env python3
"""Archive published EU listings that are confirmed full HEV (sanctions).

  python tools/archive_eu_full_hybrids.py --dry-run
  python tools/archive_eu_full_hybrids.py
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.eu_listing_check import archive_eu_listing_on_hard_skip
from app.fuel_type_labels import is_hybrid_fuel, is_pure_electric_fuel
from app.full_hybrid_exclusions import listing_is_full_hybrid
from app.models import CarListing, ListingStatus

EU_SOURCES = ("autoplius", "auto24", "mobile_de")


def _is_hybridish(listing: CarListing) -> bool:
    et = listing.engine_type or ""
    if is_pure_electric_fuel(et):
        return False
    return is_hybrid_fuel(et)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = (
            db.query(CarListing)
            .filter(
                CarListing.source.in_(EU_SOURCES),
                CarListing.status != ListingStatus.archived,
            )
            .all()
        )
        hybridish = [l for l in rows if _is_hybridish(l)]
        ban = [l for l in hybridish if listing_is_full_hybrid(l)]
        keep = [l for l in hybridish if not listing_is_full_hybrid(l)]

        ban_by: dict[str, int] = defaultdict(int)
        keep_by: dict[str, int] = defaultdict(int)
        for l in ban:
            ban_by[f"{l.brand} {l.model}"] += 1
        for l in keep:
            keep_by[f"{l.brand} {l.model}"] += 1

        print(f"eu_non_archived={len(rows)}")
        print(f"hybridish={len(hybridish)}")
        print(f"full_hev_ban={len(ban)}")
        print(f"hybrid_keep={len(keep)}")
        print("\nBAN (full HEV):")
        for name, n in sorted(ban_by.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {n:3} {name}")
        print("\nKEEP (mild/PHEV/ambiguous/e-Power):")
        for name, n in sorted(keep_by.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {n:3} {name}")

        if args.dry_run:
            print("\ndry-run: no changes")
            return 0

        archived = 0
        for listing in ban:
            if archive_eu_listing_on_hard_skip(listing):
                archived += 1
            elif listing.status != ListingStatus.archived:
                listing.status = ListingStatus.archived
                archived += 1
        db.commit()
        print(f"\narchived={archived}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
