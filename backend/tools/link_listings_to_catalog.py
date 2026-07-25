"""Backfill catalog_item_id links for existing listings."""

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
from app.listing_catalog_link import link_listing_to_catalog
from app.models import CarListing, ListingStatus


def main() -> None:
    parser = argparse.ArgumentParser(description="Link car listings to catalog modifications")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N listings (0 = all)")
    parser.add_argument("--relink", action="store_true", help="Recompute links even when catalog_item_id is set")
    parser.add_argument("--include-archived", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(CarListing).order_by(CarListing.id.asc())
        if not args.include_archived:
            query = query.filter(CarListing.status == ListingStatus.published)
        if args.limit > 0:
            query = query.limit(args.limit)

        linked = 0
        cleared = 0
        unchanged = 0
        for listing in query.all():
            previous_id = listing.catalog_item_id
            if args.relink:
                listing.catalog_item_id = None
            item = link_listing_to_catalog(db, listing)
            new_id = item.id if item else None
            if new_id == previous_id:
                unchanged += 1
                continue
            if new_id:
                linked += 1
            elif previous_id:
                cleared += 1

        if args.dry_run:
            db.rollback()
            print(f"DRY RUN linked={linked} cleared={cleared} unchanged={unchanged}")
        else:
            db.commit()
            print(f"linked={linked} cleared={cleared} unchanged={unchanged}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
