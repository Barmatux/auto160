"""Delete Mercedes-Benz 1.6 diesel 160 hp (2016+) from catalog and archive listings.

These cars are 118 kW and do not qualify for RF preferential recycling fee (утильсбор).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.logging_setup import setup_logging
from app.models import CarListing, CatalogItem, ListingStatus
from app.util_sbor_exclusions import (
    catalog_item_is_mercedes_16_diesel_160_util_exclusion,
    listing_is_mercedes_16_diesel_160_util_exclusion,
)

logger = logging.getLogger(__name__)


def remove_mercedes_16_diesel_160(*, dry_run: bool = False) -> dict[str, int | list[int]]:
    db = SessionLocal()
    stats: dict[str, int | list[int]] = {
        "catalog_items": 0,
        "catalog_item_ids": [],
        "listings_archived": 0,
        "listing_ids": [],
        "listings_cleared_links": 0,
    }
    try:
        mercedes_catalog = (
            db.query(CatalogItem)
            .filter(
                CatalogItem.source_site == "av.by",
                CatalogItem.make.ilike("%mercedes%"),
            )
            .order_by(CatalogItem.id.asc())
            .all()
        )
        catalog_items = [
            item for item in mercedes_catalog if catalog_item_is_mercedes_16_diesel_160_util_exclusion(item)
        ]
        catalog_item_ids = [item.id for item in catalog_items]
        stats["catalog_items"] = len(catalog_item_ids)
        stats["catalog_item_ids"] = catalog_item_ids

        listings_candidates = (
            db.query(CarListing)
            .filter(CarListing.brand.ilike("%mercedes%"))
            .order_by(CarListing.id.asc())
            .all()
        )
        matched_listings: dict[int, CarListing] = {}
        for listing in listings_candidates:
            if listing_is_mercedes_16_diesel_160_util_exclusion(listing):
                matched_listings[listing.id] = listing

        if catalog_item_ids:
            for listing in (
                db.query(CarListing)
                .filter(CarListing.catalog_item_id.in_(catalog_item_ids))
                .order_by(CarListing.id.asc())
                .all()
            ):
                matched_listings[listing.id] = listing

        stats["listing_ids"] = sorted(matched_listings)

        for listing in matched_listings.values():
            if listing.catalog_item_id in catalog_item_ids:
                stats["listings_cleared_links"] = int(stats["listings_cleared_links"]) + 1
                if not dry_run:
                    listing.catalog_item_id = None
            if listing.status == ListingStatus.published:
                stats["listings_archived"] = int(stats["listings_archived"]) + 1
                if not dry_run:
                    listing.status = ListingStatus.archived

        logger.info(
            "remove-mercedes-16-diesel-160: catalog_ids=%s listing_ids=%s dry_run=%s",
            catalog_item_ids,
            stats["listing_ids"],
            dry_run,
        )

        if not dry_run:
            for item in catalog_items:
                db.delete(item)
            db.commit()
        else:
            db.rollback()

        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    setup_logging("maintenance")
    parser = argparse.ArgumentParser(
        description=(
            "Delete Mercedes-Benz 1.6 diesel 160 hp catalog mods (2016+) "
            "and archive matching published listings"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stats = remove_mercedes_16_diesel_160(dry_run=args.dry_run)
    print(
        "catalog_items={catalog_items} ids={catalog_item_ids} "
        "listings_archived={listings_archived} listing_ids={listing_ids} "
        "listings_cleared_links={listings_cleared_links} dry_run={dry_run}".format(
            dry_run=args.dry_run,
            **stats,
        )
    )


if __name__ == "__main__":
    main()
