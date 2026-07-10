"""Fetch and save VIN from av.by for imported listings.

Uses vin_test service account (30 checks/day).

Examples:
  python tools/fetch_avby_vin.py --avby-id 135469319
  python tools/fetch_avby_vin.py --limit 5
  python tools/fetch_avby_vin.py --listing-id 42
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os

os.chdir(ROOT_DIR)

from app.avby_accounts import get_vin_test_account, vin_checks_remaining
from app.avby_vin import AvbyVinError, get_or_fetch_listing_vin
from app.db import SessionLocal
from app.models import CarListing


def pick_listings(db, *, listing_id: int | None, avby_id: int | None, limit: int) -> list[CarListing]:
    if listing_id:
        row = db.query(CarListing).filter(CarListing.id == listing_id).first()
        return [row] if row else []

    q = db.query(CarListing).filter(CarListing.avby_id.isnot(None), CarListing.vin.is_(None))
    if avby_id:
        q = q.filter(CarListing.avby_id == avby_id)
    return q.order_by(CarListing.id.asc()).limit(limit).all()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch VIN from av.by and save to car_listings")
    parser.add_argument("--listing-id", type=int, help="Internal listing id")
    parser.add_argument("--avby-id", type=int, help="av.by offer id")
    parser.add_argument("--limit", type=int, default=1, help="Max listings to process (default 1)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch but do not save to DB")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        account = get_vin_test_account(db)
        if account is None:
            raise SystemExit("No vin_test account in DB. Run import_avby_vin_test_account.py first.")

        remaining = vin_checks_remaining(account)
        print(f"vin_test account: {account.email} status={account.status}")
        print(f"checks remaining today: {remaining if remaining is not None else 'unlimited'}")

        listings = pick_listings(db, listing_id=args.listing_id, avby_id=args.avby_id, limit=args.limit)
        if not listings and args.avby_id:
            listing = db.query(CarListing).filter(CarListing.avby_id == args.avby_id).first()
            listings = [listing] if listing else []

        if not listings:
            raise SystemExit("No matching listings found")

        ok = 0
        for listing in listings:
            if args.dry_run and listing.vin:
                print(f"listing #{listing.id} already has vin={listing.vin}")
                ok += 1
                continue
            try:
                result = get_or_fetch_listing_vin(db, listing)
            except AvbyVinError as exc:
                print(f"listing #{listing.id} failed: {exc}")
                continue
            print(
                f"listing #{listing.id} avby_id={listing.avby_id} "
                f"vin={result.vin!r} source={result.source} cached={result.cached}"
            )
            ok += 1

        print(f"\nDone: {ok}/{len(listings)} VIN(s)")
        if account:
            db.refresh(account)
            remaining_after = vin_checks_remaining(account)
            if remaining_after is not None:
                print(f"checks remaining today: {remaining_after}")
        return 0 if ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
