#!/usr/bin/env python3
"""Backfill Europe listing feed timestamps from scrape first_seen_at.

Sets avby_published_at / avby_renewed_at so /listings/eu sorts by source appearance
across auto24 / autoplius / mobile_de instead of local import batch time.

Bulk-seed first_seen values (same timestamp on many scrape rows) fall back to
local created_at so early autoplius rows do not all pile on one day.

Example:

  python tools/backfill_europe_source_times.py --dry-run
  python tools/backfill_europe_source_times.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.config import settings
from app.db import SessionLocal
from app.listing_source_time import apply_scrape_source_timestamps, detect_bulk_first_seen
from app.models import CarListing

SOURCES = ("auto24", "autoplius", "mobile_de")

SELECT_SQL = """
SELECT source, external_id, first_seen_at, last_seen_at, updated_at
FROM listings
WHERE source = ANY(%s)
  AND external_id IS NOT NULL
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill Europe source appearance timestamps")
    parser.add_argument("--dsn", default=os.getenv("AUTOPLIUS_SCRAPE_DSN") or settings.autoplius_scrape_dsn)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = psycopg2.connect(args.dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SELECT_SQL, (list(SOURCES),))
            scrape_rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    bulk_first_seen = detect_bulk_first_seen(scrape_rows)
    print(f"scrape_rows={len(scrape_rows)} bulk_first_seen_keys={len(bulk_first_seen)}")

    by_key: dict[tuple[str, str], dict] = {}
    for row in scrape_rows:
        source = (row.get("source") or "").strip()
        external_id = str(row.get("external_id") or "").strip()
        if not source or not external_id:
            continue
        by_key[(source, external_id)] = row

    db = SessionLocal()
    updated = missing = unchanged = bulk_fallback = 0
    try:
        listings = (
            db.query(CarListing)
            .filter(CarListing.source.in_(SOURCES), CarListing.external_id.isnot(None))
            .all()
        )
        print(f"local_listings={len(listings)}")
        for listing in listings:
            key = (listing.source or "", str(listing.external_id or "").strip())
            row = by_key.get(key)
            if row is None:
                missing += 1
                continue
            before = (listing.avby_published_at, listing.avby_renewed_at)
            apply_scrape_source_timestamps(listing, row, bulk_first_seen=bulk_first_seen)
            after = (listing.avby_published_at, listing.avby_renewed_at)
            if after != before and listing.created_at and after[0] == listing.created_at:
                bulk_fallback += 1
            if after == before:
                unchanged += 1
            else:
                updated += 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    print(
        f"done dry_run={args.dry_run} updated={updated} unchanged={unchanged} "
        f"bulk_fallback={bulk_fallback} missing_scrape={missing}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
