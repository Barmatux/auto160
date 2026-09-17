"""Backfill missing cover_photo_url / raw_photos from public av.by pages into S3."""

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

from app.avby_photo_store import is_avby_s3_media_url, store_avby_listing_photos
from app.avby_public_photos import fetch_avby_public_photos
from app.db import SessionLocal
from app.logging_setup import setup_logging
from app.models import CarListing, ListingStatus

logger = logging.getLogger(__name__)


def _needs_photo_backfill(row: CarListing, *, migrate_cdn: bool) -> bool:
    if not (row.cover_photo_url or row.raw_photos):
        return True
    if not migrate_cdn:
        return False
    if is_avby_s3_media_url(row.cover_photo_url):
        return False
    cover = (row.cover_photo_url or "").strip()
    return cover.startswith("http") or bool(row.raw_photos)


def backfill_photos(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    delay: float = 0.3,
    migrate_cdn: bool = False,
) -> dict[str, int]:
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
        candidates = [row for row in rows if _needs_photo_backfill(row, migrate_cdn=migrate_cdn)]
        stats["candidates"] = len(candidates)
        if limit is not None:
            candidates = candidates[:limit]

        logger.info(
            "backfill-photos-start: candidates=%s dry_run=%s migrate_cdn=%s",
            len(candidates),
            dry_run,
            migrate_cdn,
        )

        for listing in candidates:
            avby_id = listing.avby_id
            if avby_id is None:
                stats["skipped"] += 1
                continue

            cover = listing.cover_photo_url
            raw_photos = listing.raw_photos if isinstance(listing.raw_photos, list) else None

            if not (cover or raw_photos):
                result = fetch_avby_public_photos(avby_id, listing.source_url)
                if result is None:
                    stats["failed"] += 1
                    logger.debug("no photos listing #%s avby_id=%s", listing.id, avby_id)
                    if delay > 0:
                        time.sleep(delay)
                    continue
                cover, raw_photos = result

            if dry_run:
                stats["updated"] += 1
                logger.info(
                    "would-update listing #%s avby_id=%s photos=%s",
                    listing.id,
                    avby_id,
                    len(raw_photos or []),
                )
            else:
                stored_cover, stored_raw = store_avby_listing_photos(
                    avby_id,
                    cover,
                    raw_photos if isinstance(raw_photos, list) else None,
                )
                listing.cover_photo_url = (stored_cover or cover or "")[:500] or None
                listing.raw_photos = stored_raw or raw_photos or listing.raw_photos
                stats["updated"] += 1
                logger.info(
                    "updated listing #%s avby_id=%s photos=%s",
                    listing.id,
                    avby_id,
                    len(listing.raw_photos or []),
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
    parser = argparse.ArgumentParser(description="Backfill listing photos from av.by into Autoplius S3")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument(
        "--migrate-cdn",
        action="store_true",
        help="Also re-upload listings that still point at avcdn URLs",
    )
    args = parser.parse_args()
    stats = backfill_photos(
        dry_run=args.dry_run,
        limit=args.limit,
        delay=max(0.0, args.delay),
        migrate_cdn=args.migrate_cdn,
    )
    print(stats)


if __name__ == "__main__":
    main()
