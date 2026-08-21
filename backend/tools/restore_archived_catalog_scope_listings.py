"""Restore archived av.by listings that now match catalog scope."""

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
from app.listing_archive_scope import restore_archived_listings_in_catalog_scope
from app.listing_catalog_link import link_listing_to_catalog
from app.models import CarListing, ListingStatus


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore archived av.by listings that now fit catalog make/model/generation",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--relink", action="store_true", help="Link restored listings to catalog items")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = restore_archived_listings_in_catalog_scope(db, dry_run=args.dry_run)
        restored_count = int(stats["restored"])
        print(
            "restore-archived: "
            f"checked={stats['checked']} restored={restored_count} "
            f"still_non_catalog={stats['still_non_catalog']} "
            f"still_wrong_generation={stats['still_wrong_generation']} "
            f"skipped_overpowered={stats['skipped_overpowered']} dry_run={args.dry_run}"
        )
        if args.dry_run:
            db.rollback()
            return

        if args.relink and restored_count:
            restored_ids = stats["restored_ids"]
            linked = 0
            for listing_id in restored_ids:
                listing = db.get(CarListing, listing_id)
                if listing and link_listing_to_catalog(db, listing):
                    linked += 1
            db.commit()
            print(f"restore-archived: relinked={linked}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
