#!/usr/bin/env python3
"""Drop archived / banned-hybrid leftovers from the EU CHECK queue.

  python tools/cleanup_eu_check_queue.py --dry-run
  python tools/cleanup_eu_check_queue.py
"""

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
from app.eu_listing_check import EU_CHECK_QUEUE_STATUSES, EU_CHECK_SOURCES, archive_eu_listing_on_hard_skip
from app.full_hybrid_exclusions import listing_is_banned_eu_hybrid
from app.models import CarListing, ListingStatus


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = (
            db.query(CarListing)
            .filter(
                CarListing.source.in_(EU_CHECK_SOURCES),
                CarListing.eu_check_status.in_(EU_CHECK_QUEUE_STATUSES),
            )
            .all()
        )
        clear_archived = [l for l in rows if l.status == ListingStatus.archived]
        ban_live = [
            l
            for l in rows
            if l.status != ListingStatus.archived and listing_is_banned_eu_hybrid(l)
        ]

        print(f"queue_rows={len(rows)}")
        print(f"clear_archived_check={len(clear_archived)}")
        print(f"archive_banned_live={len(ban_live)}")
        for listing in clear_archived[:30]:
            print(f"  clear\t{listing.id}\t{listing.brand} {listing.model}\t{listing.status}")
        for listing in ban_live[:30]:
            print(f"  ban\t{listing.id}\t{listing.brand} {listing.model}\t{listing.status}")

        if args.dry_run:
            print("dry-run: no changes")
            return 0

        changed = 0
        for listing in clear_archived:
            listing.eu_check_status = None
            listing.eu_check_reason = None
            changed += 1
        for listing in ban_live:
            if archive_eu_listing_on_hard_skip(listing):
                changed += 1
        db.commit()
        print(f"changed={changed}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
