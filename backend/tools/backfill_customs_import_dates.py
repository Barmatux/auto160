#!/usr/bin/env python3
"""Nightly / on-demand customs (GTK) import-date lookup for listings that already have a VIN.

Does not call av.by paid /vin — only Belarus customs scrape for VINs we already store.

Examples:

  python tools/backfill_customs_import_dates.py --dry-run
  python tools/backfill_customs_import_dates.py --limit 50 --delay 1.5
  python tools/backfill_customs_import_dates.py --force --limit 10
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.customs_vin import (
    DATABASE_PERSONAL,
    CustomsVinError,
    has_fresh_customs_check,
    lookup_customs_vin,
    normalize_vin,
    vin_is_valid,
)
from app.db import SessionLocal
from app.models import CarListing, ListingStatus, VinCustomsCheck


@dataclass
class Candidate:
    vin: str
    listing_ids: list[int]


def _existing_check(db: Session, vin: str) -> VinCustomsCheck | None:
    return (
        db.query(VinCustomsCheck)
        .filter(
            VinCustomsCheck.vin == vin,
            VinCustomsCheck.database == DATABASE_PERSONAL,
        )
        .first()
    )


def _needs_lookup(
    db: Session,
    vin: str,
    *,
    force: bool,
    only_missing_date: bool,
) -> bool:
    cached = _existing_check(db, vin)
    if force:
        if only_missing_date and cached and cached.found and cached.release_date:
            return False
        return True

    if only_missing_date:
        if cached is None:
            return True
        if cached.found and cached.release_date:
            return False
        # Missing date or not found — refresh only when cache is stale.
        return not has_fresh_customs_check(db, vin, database=DATABASE_PERSONAL)

    return not has_fresh_customs_check(db, vin, database=DATABASE_PERSONAL)


def _collect_candidates(
    db: Session,
    *,
    include_archived: bool,
    only_missing_date: bool,
    force: bool,
    limit: int,
) -> list[Candidate]:
    query = db.query(CarListing.id, CarListing.vin).filter(
        CarListing.vin.isnot(None),
        func.length(func.trim(CarListing.vin)) == 17,
    )
    if not include_archived:
        query = query.filter(CarListing.status != ListingStatus.archived)

    rows = query.order_by(CarListing.id.desc()).all()

    by_vin: dict[str, list[int]] = {}
    for listing_id, raw_vin in rows:
        vin = normalize_vin(raw_vin)
        if not vin_is_valid(vin):
            continue
        by_vin.setdefault(vin, []).append(int(listing_id))

    candidates: list[Candidate] = []
    for vin, listing_ids in by_vin.items():
        if not _needs_lookup(db, vin, force=force, only_missing_date=only_missing_date):
            continue
        candidates.append(Candidate(vin=vin, listing_ids=listing_ids))

    def _priority(item: Candidate) -> tuple[int, int]:
        cached = _existing_check(db, item.vin)
        if cached is None:
            return (0, -max(item.listing_ids))
        if cached.found and not cached.release_date:
            return (1, -max(item.listing_ids))
        if not cached.found:
            return (2, -max(item.listing_ids))
        return (3, -max(item.listing_ids))

    candidates.sort(key=_priority)
    if limit and limit > 0:
        candidates = candidates[:limit]
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lookup customs import dates (GTK) for listings that already have a VIN"
    )
    parser.add_argument("--limit", type=int, default=0, help="Max unique VINs to check (0 = all)")
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between live GTK requests (not applied to cache hits)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cache TTL and re-query GTK for every candidate",
    )
    parser.add_argument(
        "--only-missing-date",
        action="store_true",
        help="Prefer VINs with no release_date yet (still respects cache unless --force)",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Also process archived listings",
    )
    parser.add_argument("--dry-run", action="store_true", help="List candidates without GTK calls")
    args = parser.parse_args()

    db = SessionLocal()
    stats: Counter[str] = Counter()
    try:
        candidates = _collect_candidates(
            db,
            include_archived=args.include_archived,
            only_missing_date=args.only_missing_date,
            force=args.force,
            limit=args.limit,
        )
        print(
            f"candidates={len(candidates)} force={args.force} "
            f"only_missing_date={args.only_missing_date} dry_run={args.dry_run}"
        )
        if args.dry_run:
            for item in candidates[:30]:
                print(f"  {item.vin} listings={item.listing_ids[:5]}")
            if len(candidates) > 30:
                print(f"  ... and {len(candidates) - 30} more")
            return 0

        for index, item in enumerate(candidates, start=1):
            try:
                result = lookup_customs_vin(
                    db,
                    item.vin,
                    database=DATABASE_PERSONAL,
                    force_refresh=args.force,
                )
            except CustomsVinError as exc:
                stats["error"] += 1
                print(f"[{index}/{len(candidates)}] {item.vin} ERROR {exc}")
                time.sleep(max(0.0, args.delay))
                continue

            if result.cached:
                stats["cached"] += 1
                tag = "cached"
            else:
                stats["fetched"] += 1
                tag = "fetched"
                time.sleep(max(0.0, args.delay))

            if result.found and result.release_date:
                stats["found_with_date"] += 1
                print(
                    f"[{index}/{len(candidates)}] {item.vin} {tag} "
                    f"found date={result.release_date} listings={len(item.listing_ids)}"
                )
            elif result.found:
                stats["found_no_date"] += 1
                print(
                    f"[{index}/{len(candidates)}] {item.vin} {tag} "
                    f"found_no_date listings={len(item.listing_ids)}"
                )
            else:
                stats["not_found"] += 1
                print(
                    f"[{index}/{len(candidates)}] {item.vin} {tag} "
                    f"not_found listings={len(item.listing_ids)}"
                )
    finally:
        db.close()

    print(
        "done "
        + " ".join(f"{key}={stats[key]}" for key in sorted(stats))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
