"""Print published listings with GTK release date."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.models import CarListing, ListingStatus, VinCustomsCheck


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db = SessionLocal()
    try:
        rows = (
            db.query(CarListing, VinCustomsCheck)
            .join(VinCustomsCheck, CarListing.vin == VinCustomsCheck.vin)
            .filter(
                CarListing.status == ListingStatus.published,
                VinCustomsCheck.found.is_(True),
                VinCustomsCheck.release_date.isnot(None),
                VinCustomsCheck.release_date != "",
                VinCustomsCheck.database == "personal_free_circulation",
            )
            .order_by(VinCustomsCheck.checked_at.desc())
            .limit(10)
            .all()
        )
        print(f"count={len(rows)}")
        for listing, check in rows:
            print(
                f"id={listing.id} | {listing.brand} {listing.model} {listing.year} | "
                f"release={check.release_date} | https://auto160.ru/listings/{listing.id}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    main()
