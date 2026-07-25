"""Backfill VIN metadata via authenticated GET /offer-types/cars/offers/{id}."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_offer_metadata import enrich_listings_vin_metadata
from app.db import SessionLocal
from app.listing_enrichment import listing_has_saved_vin
from app.models import CarListing, ListingStatus


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill av.by offer VIN metadata for listings")
    parser.add_argument("--limit", type=int, default=200, help="Max listings to process (0=all)")
    parser.add_argument("--only-missing-vin", action="store_true", help="Skip listings that already have VIN")
    parser.add_argument("--dry-run", action="store_true", help="List candidates only")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = (
            db.query(CarListing)
            .filter(
                CarListing.avby_id.isnot(None),
                CarListing.status == ListingStatus.published,
            )
            .order_by(CarListing.updated_at.desc())
        )
        if args.only_missing_vin:
            rows = [row for row in query.all() if not listing_has_saved_vin(row)]
        else:
            rows = query.all()

        if args.limit and args.limit > 0:
            rows = rows[: args.limit]

        print(f"candidates: {len(rows)}")
        if args.dry_run:
            return 0

        stats = enrich_listings_vin_metadata(db, rows, limit=len(rows) if args.limit == 0 else args.limit)
        print(
            f"done: eligible={stats.eligible} attempted={stats.attempted} "
            f"fetched={stats.fetched} vin_saved={stats.vin_saved} "
            f"indicated_updated={stats.indicated_updated} errors={len(stats.errors)}"
        )
        for err in stats.errors[:10]:
            print(f"  error: {err}")
        return 0 if not stats.errors else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
