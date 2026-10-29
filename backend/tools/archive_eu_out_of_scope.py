#!/usr/bin/env python3
"""Archive EU listings that are out of Auto160 scope (excluded brands / non-car body).

  python tools/archive_eu_out_of_scope.py --dry-run
  python tools/archive_eu_out_of_scope.py
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

from app.body_type_labels import is_hidden_body_type
from app.brand_exclusions import is_excluded_brand
from app.db import SessionLocal
from app.eu_listing_check import archive_eu_listing_on_hard_skip
from app.models import CarListing, ListingStatus

EU_SOURCES = ("autoplius", "auto24", "mobile_de")


def _reason(listing: CarListing) -> str | None:
    if is_excluded_brand(listing.brand):
        return f"brand:{listing.brand}"
    if is_hidden_body_type(listing.body_type):
        return f"body:{listing.body_type}"
    return None


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
        ban = [(l, _reason(l)) for l in rows if _reason(l)]
        by_reason: dict[str, int] = defaultdict(int)
        for _, reason in ban:
            by_reason[reason or "?"] += 1

        print(f"eu_non_archived={len(rows)}")
        print(f"out_of_scope={len(ban)}")
        print("\nBY reason:")
        for name, n in sorted(by_reason.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {n:3} {name}")
        print("\nDETAIL:")
        for listing, reason in sorted(ban, key=lambda x: (x[1] or "", x[0].id)):
            print(
                f"  {listing.id}\t{listing.source}\t{listing.brand} {listing.model}\t"
                f"{listing.body_type}\t{reason}\t{listing.title}"
            )

        if args.dry_run:
            print("\ndry-run: no changes")
            return 0

        archived = 0
        for listing, _ in ban:
            if archive_eu_listing_on_hard_skip(listing):
                archived += 1
        db.commit()
        print(f"\narchived={archived}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
