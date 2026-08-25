"""Backfill catalog_items.has_7_seats from raw_specs.modification_detail.numberOfSeats."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.models import CatalogItem
from app.seat_labels import has_7_seats_from_raw


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill has_7_seats on catalog_items")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        updated = 0
        checked = 0
        for item in db.query(CatalogItem).yield_per(500):
            checked += 1
            desired = has_7_seats_from_raw(raw_specs=item.raw_specs if isinstance(item.raw_specs, dict) else None)
            if bool(item.has_7_seats) == desired:
                continue
            updated += 1
            if not args.dry_run:
                item.has_7_seats = desired
            if updated % 500 == 0 and not args.dry_run:
                db.commit()
        if not args.dry_run:
            db.commit()
        print(f"backfill-has-7-seats: checked={checked} updated={updated} dry_run={args.dry_run}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
