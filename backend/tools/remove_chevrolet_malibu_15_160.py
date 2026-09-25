"""Delete Chevrolet Malibu 1.5 L / 160 hp from catalog and archive listings.

These cars do not qualify for RF preferential recycling fee (утильсбор).
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
    catalog_item_is_chevrolet_malibu_15_160_util_exclusion,
    listing_is_chevrolet_malibu_15_160_util_exclusion,
)

logger = logging.getLogger(__name__)


def remove_chevrolet_malibu_15_160(*, dry_run: bool = False) -> dict[str, int | list[int]]:
    db = SessionLocal()
    stats: dict[str, int | list[int]] = {
        "catalog_items": 0,
        "catalog_item_ids": [],
        "listings_archived": 0,
        "listing_ids": [],
        "listings_cleared_links": 0,
    }
    try:
        chevrolet_catalog = (
            db.query(CatalogItem)
            .filter(
                CatalogItem.source_site == "av.by",
                CatalogItem.make.ilike("%chevrolet%"),
                CatalogItem.model.ilike("%malibu%"),
            )
            .order_by(CatalogItem.id.asc())
            .all()
        )
        catalog_items = [
            item for item in chevrolet_catalog if catalog_item_is_chevrolet_malibu_15_160_util_exclusion(item)
        ]
        catalog_item_ids = [item.id for item in catalog_items]
        stats["catalog_items"] = len(catalog_item_ids)
        stats["catalog_item_ids"] = catalog_item_ids

        listings_candidates = (
            db.query(CarListing)
            .filter(
                CarListing.brand.ilike("%chevrolet%"),
                CarListing.model.ilike("%malibu%"),
            )
            .order_by(CarListing.id.asc())
            .all()
        )
        matched_listings: dict[int, CarListing] = {}
        for listing in listings_candidates:
            if listing_is_chevrolet_malibu_15_160_util_exclusion(listing):
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
            "remove-chevrolet-malibu-15-160: catalog_ids=%s listing_ids=%s dry_run=%s",
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
            "Delete Chevrolet Malibu 1.5 L / 160 hp catalog mods "
            "and archive matching published listings"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    stats = remove_chevrolet_malibu_15_160(dry_run=args.dry_run)
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
