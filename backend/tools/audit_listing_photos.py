"""Report listings missing cover photos."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.models import CarListing, ListingStatus


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db = SessionLocal()
    try:
        published = db.query(CarListing).filter(CarListing.status == ListingStatus.published).all()
        missing = [row for row in published if not (row.cover_photo_url or row.raw_photos)]
        with_cover = len(published) - len(missing)
        print(f"published={len(published)} with_cover_or_raw={with_cover} missing_both={len(missing)}")
        for row in missing[:20]:
            print(f"  #{row.id} {row.brand} {row.model} {row.year} avby_id={row.avby_id}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
    finally:
        db.close()


if __name__ == "__main__":
    main()
