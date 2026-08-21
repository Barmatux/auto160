"""Fix listing prices where Russian rubles were stored as BYN."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_price import fix_rub_stored_as_byn
from app.db import SessionLocal
from app.models import CarListing


def main() -> None:
    parser = argparse.ArgumentParser(description="Correct mis-stored listing prices (RUB saved as BYN)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    checked = 0
    updated = 0
    try:
        rows = db.query(CarListing).filter(CarListing.avby_id.isnot(None)).order_by(CarListing.id.asc()).all()
        for listing in rows:
            checked += 1
            corrected = fix_rub_stored_as_byn(listing.price)
            if corrected is None or corrected == float(listing.price):
                continue
            print(
                f"listing={listing.id} avby={listing.avby_id}: "
                f"{float(listing.price):,.0f} -> {corrected:,.0f} BYN"
            )
            updated += 1
            if not args.dry_run:
                listing.price = corrected
        if updated and not args.dry_run:
            db.commit()
        print(f"backfill-prices: checked={checked} updated={updated} dry_run={args.dry_run}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
