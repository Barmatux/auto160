#!/usr/bin/env python3
"""Restore business-org listings wrongly archived by catalog prune."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.models import CarListing, ListingStatus

DEFAULT_MAX_HP_PUBLIC = 160


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--listing-id", type=int, default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        q = db.query(CarListing).filter(
            CarListing.organization_id.isnot(None),
            CarListing.status == ListingStatus.archived,
            CarListing.source == "av.by",
        )
        if args.listing_id is not None:
            q = q.filter(CarListing.id == args.listing_id)
        rows = q.all()
        published = draft = 0
        for listing in rows:
            hp = listing.engine_power_hp
            if hp is None or int(hp) > DEFAULT_MAX_HP_PUBLIC or listing.price_byn_missing:
                target = ListingStatus.draft
                draft += 1
            else:
                target = ListingStatus.published
                published += 1
            print(
                f"#{listing.id} avby={listing.avby_id} hp={hp} "
                f"{listing.brand} {listing.model} -> {target.value}"
            )
            if not args.dry_run:
                listing.status = target
        if not args.dry_run:
            db.commit()
        print(f"restored published={published} draft={draft} dry_run={args.dry_run}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
