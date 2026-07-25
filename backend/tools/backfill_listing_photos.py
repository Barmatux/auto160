"""Backfill missing cover_photo_url / raw_photos from public av.by pages."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_public_photos import fetch_avby_public_photos
from app.db import SessionLocal
from app.logging_setup import setup_logging
from app.models import CarListing, ListingStatus

logger = logging.getLogger(__name__)


def backfill_photos(*, dry_run: bool = False, limit: int | None = None, delay: float = 0.3) -> dict[str, int]:
    db = SessionLocal()
    stats = {"candidates": 0, "updated": 0, "skipped": 0, "failed": 0}
    try:
        query = (
            db.query(CarListing)
            .filter(
                CarListing.status == ListingStatus.published,
                CarListing.avby_id.isnot(None),
            )
            .order_by(CarListing.id.asc())
        )
        rows = query.all()
        candidates = [
            row
            for row in rows
            if not (row.cover_photo_url or row.raw_photos)
        ]
        stats["candidates"] = len(candidates)
        if limit is not None:
            candidates = candidates[:limit]

        logger.info("backfill-photos-start: candidates=%s dry_run=%s", len(candidates), dry_run)

        for listing in candidates:
            avby_id = listing.avby_id
            if avby_id is None:
                stats["skipped"] += 1
                continue

            result = fetch_avby_public_photos(avby_id, listing.source_url)
            if result is None:
                stats["failed"] += 1
                logger.debug("no photos listing #%s avby_id=%s", listing.id, avby_id)
            else:
                cover, raw_photos = result
                if not dry_run:
                    listing.cover_photo_url = (cover or listing.cover_photo_url or "")[:500] or None
                    listing.raw_photos = raw_photos or listing.raw_photos
                stats["updated"] += 1
                logger.info(
                    "updated listing #%s avby_id=%s photos=%s",
                    listing.id,
                    avby_id,
                    len(raw_photos or []),
                )

            if delay > 0:
                time.sleep(delay)

        if dry_run:
            db.rollback()
        else:
            db.commit()

        logger.info("backfill-photos-finish: %s", stats)
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    setup_logging("avby-sync")
    parser = argparse.ArgumentParser(description="Backfill listing photos from av.by public pages")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()
    stats = backfill_photos(dry_run=args.dry_run, limit=args.limit, delay=max(0.0, args.delay))
    print(stats)


if __name__ == "__main__":
    main()
