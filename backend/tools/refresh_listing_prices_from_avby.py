"""Refresh listing BYN prices directly from av.by advert pages."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_price import fetch_price_byn_from_avby_public_url
from app.db import SessionLocal
from app.listing_missing_byn import apply_import_byn_price_state
from app.models import CarListing, ListingStatus


def _listing_page_url(listing: CarListing) -> str | None:
    source_url = (listing.source_url or "").strip()
    if source_url:
        return source_url
    if listing.avby_id is not None:
        return f"https://cars.av.by/{listing.avby_id}"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh BYN prices from av.by public advert pages")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--listing-id", type=int, default=None, help="Refresh a single listing id")
    parser.add_argument("--delay", type=float, default=0.15, help="Delay between page fetches")
    parser.add_argument("--limit", type=int, default=None, help="Max listings to refresh")
    args = parser.parse_args()

    db = SessionLocal()
    checked = 0
    updated = 0
    failed = 0
    try:
        query = db.query(CarListing).filter(CarListing.avby_id.isnot(None))
        if args.listing_id is not None:
            query = query.filter(CarListing.id == args.listing_id)
        else:
            query = query.filter(CarListing.status.in_([ListingStatus.published, ListingStatus.draft]))
        query = query.order_by(CarListing.id.asc())
        if args.limit is not None:
            query = query.limit(args.limit)
        rows = query.all()

        for listing in rows:
            checked += 1
            page_url = _listing_page_url(listing)
            if not page_url:
                failed += 1
                continue
            try:
                price_byn = fetch_price_byn_from_avby_public_url(page_url)
            except Exception as exc:
                failed += 1
                print(f"listing={listing.id} avby={listing.avby_id}: fetch-fail -> {exc}")
                continue

            current = float(listing.price) if listing.price is not None else None
            if price_byn is None:
                if listing.price_byn_missing and current is None:
                    continue
                print(f"listing={listing.id} avby={listing.avby_id}: mark missing BYN")
                if not args.dry_run:
                    apply_import_byn_price_state(listing, price_byn=None, price_byn_missing=True)
                updated += 1
            elif current is None or abs(current - float(price_byn)) > 0.009:
                print(
                    f"listing={listing.id} avby={listing.avby_id}: "
                    f"{current if current is not None else '—'} -> {price_byn} BYN"
                )
                if not args.dry_run:
                    apply_import_byn_price_state(listing, price_byn=price_byn, price_byn_missing=False)
                updated += 1

            if args.delay > 0:
                time.sleep(args.delay)

        if updated and not args.dry_run:
            db.commit()
        print(f"refresh-page-prices: checked={checked} updated={updated} failed={failed} dry_run={args.dry_run}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
