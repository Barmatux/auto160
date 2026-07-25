"""Archive local listings whose av.by advert is no longer public."""

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

from app.avby_offer_check import OfferCheckResult, check_avby_offer_public
from app.db import SessionLocal
from app.logging_setup import setup_logging
from app.models import CarListing, ListingStatus

logger = logging.getLogger(__name__)


def archive_removed_listings(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    delay_seconds: float = 0.5,
) -> dict[str, int]:
    db = SessionLocal()
    stats = {"checked": 0, "archived": 0, "active": 0, "unknown": 0, "skipped": 0}
    try:
        query = (
            db.query(CarListing)
            .filter(
                CarListing.status == ListingStatus.published,
                CarListing.avby_id.isnot(None),
            )
            .order_by(CarListing.id.asc())
        )
        if limit is not None:
            query = query.limit(limit)

        listings = query.all()
        logger.info("archive-check-start: published_with_avby_id=%s dry_run=%s", len(listings), dry_run)

        for listing in listings:
            avby_id = listing.avby_id
            if avby_id is None:
                stats["skipped"] += 1
                continue

            result = check_avby_offer_public(avby_id, listing.source_url)
            stats["checked"] += 1

            if result == OfferCheckResult.active:
                stats["active"] += 1
                logger.debug("keep listing #%s avby_id=%s", listing.id, avby_id)
            elif result == OfferCheckResult.removed:
                stats["archived"] += 1
                logger.info(
                    "archive listing #%s avby_id=%s url=%s",
                    listing.id,
                    avby_id,
                    listing.source_url or f"https://cars.av.by/{avby_id}",
                )
                if not dry_run:
                    listing.status = ListingStatus.archived
            else:
                stats["unknown"] += 1
                logger.warning(
                    "skip listing #%s avby_id=%s: could not verify (network or unexpected response)",
                    listing.id,
                    avby_id,
                )

            if delay_seconds > 0:
                time.sleep(delay_seconds)

        if not dry_run and stats["archived"]:
            db.commit()
        elif dry_run:
            db.rollback()
        else:
            db.commit()

        logger.info(
            "archive-check-finish: checked=%s active=%s archived=%s unknown=%s skipped=%s dry_run=%s",
            stats["checked"],
            stats["active"],
            stats["archived"],
            stats["unknown"],
            stats["skipped"],
            dry_run,
        )
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    setup_logging("avby-archive")
    parser = argparse.ArgumentParser(description="Archive listings removed from av.by")
    parser.add_argument("--dry-run", action="store_true", help="Do not write status changes")
    parser.add_argument("--limit", type=int, default=None, help="Check only first N listings")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Pause between HTTP checks in seconds (rate limiting)",
    )
    args = parser.parse_args()

    stats = archive_removed_listings(
        dry_run=args.dry_run,
        limit=args.limit,
        delay_seconds=max(0.0, args.delay),
    )
    if stats["unknown"] and not stats["archived"] and not stats["active"]:
        raise SystemExit(1)
    raise SystemExit(0)


if __name__ == "__main__":
    main()
