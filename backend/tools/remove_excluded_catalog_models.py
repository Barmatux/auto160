"""Delete excluded catalog models and archive related listings."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.catalog_exclusions import purge_excluded_catalog_and_listings
from app.db import SessionLocal
from app.logging_setup import setup_logging


def main() -> None:
    setup_logging("maintenance")
    parser = argparse.ArgumentParser(description="Remove excluded catalog models and archive related listings")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = purge_excluded_catalog_and_listings(db, dry_run=args.dry_run)
    finally:
        db.close()

    print(
        "catalog_items_deleted={catalog_items_deleted} catalog_item_ids={catalog_item_ids} "
        "listings_archived={listings_archived} listings_touched={listings_touched} "
        "listing_ids={listing_ids} dry_run={dry_run}".format(dry_run=args.dry_run, **stats)
    )


if __name__ == "__main__":
    main()
