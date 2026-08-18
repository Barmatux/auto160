"""Remove catalog modifications for a make/model/generation and archive related listings."""

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

from sqlalchemy import func

from app.db import SessionLocal
from app.listing_catalog_link import canonical_model_name, normalize_match_text
from app.logging_setup import setup_logging
from app.models import CarListing, CatalogItem, ListingStatus

logger = logging.getLogger(__name__)


def listing_matches_generation(listing_generation: str | None, target_generation: str) -> bool:
    normalized = normalize_match_text(listing_generation)
    target = normalize_match_text(target_generation)
    if not normalized or not target:
        return False
    if normalized == target:
        return True
    if normalized.endswith(f"({target})"):
        return True
    if normalized.startswith(f"{target} ") or normalized.startswith(f"{target}·"):
        return True
    return False


def find_catalog_items(db, *, make: str, model: str, generation: str) -> list[CatalogItem]:
    canonical = canonical_model_name(model)
    return (
        db.query(CatalogItem)
        .filter(
            CatalogItem.source_site == "av.by",
            CatalogItem.make.ilike(f"%{make.strip()}%"),
            CatalogItem.model == canonical,
            CatalogItem.generation == generation.strip(),
        )
        .order_by(CatalogItem.id.asc())
        .all()
    )


def remove_catalog_generation(
    *,
    make: str,
    model: str,
    generation: str,
    dry_run: bool = False,
    archive_listings: bool = True,
) -> dict[str, int | list[int]]:
    db = SessionLocal()
    stats: dict[str, int | list[int]] = {
        "catalog_items": 0,
        "catalog_item_ids": [],
        "listings_archived": 0,
        "listings_cleared_links": 0,
    }
    try:
        catalog_items = find_catalog_items(db, make=make, model=model, generation=generation)

        catalog_item_ids = [item.id for item in catalog_items]
        stats["catalog_items"] = len(catalog_item_ids)
        stats["catalog_item_ids"] = catalog_item_ids

        listings_by_catalog = []
        if catalog_item_ids:
            listings_by_catalog = (
                db.query(CarListing)
                .filter(CarListing.catalog_item_id.in_(catalog_item_ids))
                .order_by(CarListing.id.asc())
                .all()
            )

        listings_by_generation = (
            db.query(CarListing)
            .filter(
                func.lower(CarListing.brand) == make.strip().lower(),
                func.lower(CarListing.model) == model.strip().lower(),
            )
            .order_by(CarListing.id.asc())
            .all()
        )
        listings_by_generation = [
            listing
            for listing in listings_by_generation
            if listing_matches_generation(listing.generation, generation)
        ]

        listings_to_touch: dict[int, CarListing] = {}
        for listing in [*listings_by_catalog, *listings_by_generation]:
            listings_to_touch[listing.id] = listing

        for listing in listings_to_touch.values():
            if archive_listings and listing.status == ListingStatus.published:
                stats["listings_archived"] = int(stats["listings_archived"]) + 1
                if not dry_run:
                    listing.status = ListingStatus.archived
            if listing.catalog_item_id in catalog_item_ids:
                stats["listings_cleared_links"] = int(stats["listings_cleared_links"]) + 1
                if not dry_run:
                    listing.catalog_item_id = None

        logger.info(
            "remove-catalog-generation: make=%s model=%s generation=%s catalog_items=%s listings=%s dry_run=%s",
            make,
            model,
            generation,
            catalog_item_ids,
            sorted(listings_to_touch),
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
        description="Delete catalog modifications for a make/model/generation and archive related listings",
    )
    parser.add_argument("--make", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--generation", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--keep-listings",
        action="store_true",
        help="Only clear catalog links; do not archive published listings",
    )
    args = parser.parse_args()

    stats = remove_catalog_generation(
        make=args.make,
        model=args.model,
        generation=args.generation,
        dry_run=args.dry_run,
        archive_listings=not args.keep_listings,
    )
    print(
        "catalog_items={catalog_items} ids={catalog_item_ids} "
        "listings_archived={listings_archived} listings_cleared_links={listings_cleared_links} dry_run={dry_run}".format(
            dry_run=args.dry_run,
            **stats,
        )
    )


if __name__ == "__main__":
    main()
