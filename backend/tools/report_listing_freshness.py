"""Report published/archived listing counts and last archive run."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.logging_setup import log_dir
from app.models import CarListing, ListingStatus


def _read_last_archive_run() -> dict | None:
    log_file = log_dir() / "avby-archive.log"
    if not log_file.exists():
        return None
    text = log_file.read_text(encoding="utf-8", errors="replace")
    matches = re.findall(
        r"archive-check-finish: checked=(\d+) active=(\d+) archived=(\d+) unknown=(\d+)",
        text,
    )
    if not matches:
        return None
    checked, active, archived, unknown = matches[-1]
    return {
        "checked": int(checked),
        "active": int(active),
        "archived": int(archived),
        "unknown": int(unknown),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db = SessionLocal()
    try:
        published = db.query(CarListing).filter(CarListing.status == ListingStatus.published).count()
        archived = db.query(CarListing).filter(CarListing.status == ListingStatus.archived).count()
        published_avby = (
            db.query(CarListing)
            .filter(CarListing.status == ListingStatus.published, CarListing.avby_id.isnot(None))
            .count()
        )
        missing_photos = sum(
            1
            for row in db.query(CarListing)
            .filter(CarListing.status == ListingStatus.published, CarListing.avby_id.isnot(None))
            .all()
            if not (row.cover_photo_url or row.raw_photos)
        )
    finally:
        db.close()

    report = {
        "published": published,
        "published_with_avby_id": published_avby,
        "archived": archived,
        "missing_photos_avby": missing_photos,
        "last_archive_run": _read_last_archive_run(),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
