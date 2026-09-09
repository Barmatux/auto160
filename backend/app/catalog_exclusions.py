"""Make/model pairs excluded from public catalog and listings."""

from __future__ import annotations

from sqlalchemy import and_, func

from app.models import CarListing, CatalogItem, ListingStatus


def _normalize_make(value: str | None) -> str:
    return (value or "").strip().lower().replace("ё", "е")


def _normalize_model(value: str | None) -> str:
    return (value or "").strip().lower().replace("ё", "е").replace("-", " ")


def is_excluded_make_model(make: str | None, model: str | None) -> bool:
    make_n = _normalize_make(make)
    model_n = _normalize_model(model)
    if make_n != "toyota":
        return False
    return "prius" in model_n


def _catalog_exclusion_predicate():
    return and_(
        func.lower(CatalogItem.make) == "toyota",
        func.lower(CatalogItem.model).like("%prius%"),
    )


def _listing_exclusion_predicate():
    return and_(
        func.lower(CarListing.brand) == "toyota",
        func.lower(CarListing.model).like("%prius%"),
    )


def apply_catalog_exclusion_filter(query):
    return query.filter(~_catalog_exclusion_predicate())


def apply_listing_exclusion_filter(query):
    return query.filter(~_listing_exclusion_predicate())


def purge_excluded_catalog_and_listings(db, *, dry_run: bool = False) -> dict[str, int | list[int]]:
    catalog_items = (
        db.query(CatalogItem)
        .filter(CatalogItem.source_site == "av.by")
        .filter(_catalog_exclusion_predicate())
        .order_by(CatalogItem.id.asc())
        .all()
    )
    catalog_item_ids = [item.id for item in catalog_items]

    listings = (
        db.query(CarListing)
        .filter(_listing_exclusion_predicate())
        .order_by(CarListing.id.asc())
        .all()
    )

    stats: dict[str, int | list[int]] = {
        "catalog_items_deleted": len(catalog_items),
        "catalog_item_ids": catalog_item_ids,
        "listings_archived": 0,
        "listings_touched": len(listings),
        "listing_ids": [listing.id for listing in listings],
    }

    for listing in listings:
        if listing.status == ListingStatus.published:
            stats["listings_archived"] = int(stats["listings_archived"]) + 1
            if not dry_run:
                listing.status = ListingStatus.archived
        if listing.catalog_item_id in catalog_item_ids and not dry_run:
            listing.catalog_item_id = None

    if not dry_run:
        for item in catalog_items:
            db.delete(item)
        db.commit()
    else:
        db.rollback()

    return stats
