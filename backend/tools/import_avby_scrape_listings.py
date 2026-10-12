#!/usr/bin/env python3
"""Import av.by listings from scrape Postgres into Auto160 car_listings.

Reads ``listings`` where ``source='avby'`` via ``AUTOPLIUS_SCRAPE_DSN``.
Catalog / generation / util-sbor filters stay on Auto160 (post-fetch).

Example:

  python tools/import_avby_scrape_listings.py --dry-run --limit 20
  python tools/import_avby_scrape_listings.py
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_photo_store import is_avby_s3_media_url, store_avby_listing_photos
from app.avby_scrape_map import (
    DEFAULT_MAX_HP,
    DEFAULT_PRICE_USD_MIN,
    DEFAULT_YEAR_MIN,
    map_avby_scrape_row,
)
from app.body_type_labels import is_hidden_body_type
from app.catalog_visibility import listing_generation_allowed_for_model
from app.config import settings
from app.db import SessionLocal
from app.catalog_ratings import generation_key
from app.listing_archive_scope import normalize_catalog_match_name as _normalize_name
from app.listing_catalog_link import canonical_model_name, link_listing_to_catalog
from app.listing_missing_byn import apply_import_byn_price_state
from app.listing_source_time import apply_scrape_source_timestamps, detect_bulk_first_seen
from app.models import AvbySyncRun, CarListing, CatalogItem, ListingStatus, User, UserRole
from app.security import hash_password
from app.util_sbor_exclusions import listing_payload_is_util_sbor_exclusion
from app.avby_offer_metadata import enrich_listings_vin_metadata
from app.listing_enrichment import build_rating_one_targets, enrich_rating_one_listings

SCRAPE_SOURCE = "avby"
LISTING_SOURCE = "av.by"
PRESERVE_ON_UPDATE_FIELDS = frozenset({"vin", "vin_fetched_at"})

SELECT_SQL = """
SELECT
  id,
  source,
  external_id,
  url,
  title,
  year,
  body_type,
  price_eur,
  fuel,
  transmission,
  engine,
  engine_liters,
  mileage_km,
  city,
  photo_url,
  photo_urls,
  description,
  description_ru,
  phone,
  vin_masked,
  parameters,
  raw,
  detail_scraped,
  status,
  first_seen_at,
  last_seen_at,
  updated_at
FROM listings
WHERE source = %s
  AND status = 'active'
  AND detail_scraped IS TRUE
ORDER BY id DESC
"""


def _ensure_importer_user(db) -> User:
    user = db.query(User).filter(User.role == UserRole.admin).order_by(User.id.asc()).first()
    if user:
        return user
    user = db.query(User).order_by(User.id.asc()).first()
    if user:
        return user
    created = User(
        username="avby_importer",
        email="avby_importer@auto160.local",
        name="AV.BY Importer",
        role=UserRole.seller,
        password_hash=hash_password("change_me_now_123"),
    )
    db.add(created)
    db.commit()
    db.refresh(created)
    return created


def _model_match_key(model: str | None) -> str:
    """Normalize model so English '1 Series' and av.by '1 серия' share a key."""
    return _normalize_name(canonical_model_name(model) or model)


def _collect_visible_catalog_rows() -> list[CatalogItem]:
    from app.catalog_visibility import apply_visible_catalog_filter

    db = SessionLocal()
    try:
        return (
            apply_visible_catalog_filter(db.query(CatalogItem))
            .order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.id.desc())
            .all()
        )
    finally:
        db.close()


def _collect_catalog_brand_models(rows: list[CatalogItem] | None = None) -> dict[str, set[str]]:
    items = rows if rows is not None else _collect_visible_catalog_rows()
    brand_to_models: dict[str, set[str]] = {}
    for item in items:
        make = (item.make or "").strip()
        model = (item.model or "").strip()
        if not make or not model:
            continue
        brand_to_models.setdefault(_normalize_name(make), set()).add(_model_match_key(model))
    return brand_to_models


def _build_generation_index(rows: list[CatalogItem]) -> dict[tuple[str, str], tuple[frozenset[str], bool]]:
    index: dict[tuple[str, str], tuple[set[str], bool]] = {}
    for item in rows:
        make = (item.make or "").strip()
        model = (item.model or "").strip()
        if not make or not model:
            continue
        key = (_normalize_name(make), _model_match_key(model))
        generations, allows_unrated = index.get(key, (set(), False))
        gen = generation_key(item.generation)
        if gen:
            generations.add(gen)
        else:
            allows_unrated = True
        index[key] = (generations, allows_unrated)
    return {
        key: (frozenset(gens), allows_unrated)
        for key, (gens, allows_unrated) in index.items()
    }


def _is_in_catalog(brand_n: str, model_n: str, brand_to_models: dict[str, set[str]]) -> bool:
    return brand_n in brand_to_models and model_n in brand_to_models[brand_n]


def _is_business_org_listing(listing: CarListing) -> bool:
    return listing.organization_id is not None


def _load_existing_avby_map(db) -> dict[int, CarListing]:
    rows = db.query(CarListing).filter(CarListing.avby_id.isnot(None)).all()
    return {int(row.avby_id): row for row in rows if row.avby_id is not None}


def _start_sync_run(db, *, trigger: str, max_hp: int, dry_run: bool) -> AvbySyncRun | None:
    if dry_run:
        return None
    run = AvbySyncRun(status="running", trigger=trigger, max_hp=max_hp, dry_run=dry_run)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _finish_sync_run(
    db,
    run: AvbySyncRun | None,
    *,
    status: str,
    models_count: int,
    brands_count: int,
    created: int,
    updated: int,
    skipped: int,
    skipped_by_hp: int,
    failed_brands: int = 0,
    pages_fetched: int = 0,
    error_message: str | None = None,
) -> None:
    if run is None:
        return
    run.finished_at = datetime.now(UTC).replace(tzinfo=None)
    run.status = status
    run.models_count = models_count
    run.brands_count = brands_count
    run.created_count = created
    run.updated_count = updated
    run.skipped_count = skipped
    run.skipped_by_hp_count = skipped_by_hp
    run.failed_brands_count = failed_brands
    run.pages_fetched_count = pages_fetched
    run.error_message = error_message
    db.commit()


def _resolve_photos(mapped, existing: CarListing | None) -> tuple[str | None, list[dict] | None]:
    if mapped.photo_urls and mapped.cover_photo_url and is_avby_s3_media_url(mapped.cover_photo_url):
        raw = [{"url": url, "main": index == 0} for index, url in enumerate(mapped.photo_urls)]
        return mapped.cover_photo_url, raw
    if (
        existing
        and is_avby_s3_media_url(existing.cover_photo_url)
        and isinstance(existing.raw_photos, list)
        and existing.raw_photos
    ):
        return existing.cover_photo_url, existing.raw_photos

    raw_from_source = [{"url": url} for url in (mapped.source_photo_urls or []) if url]
    cover_http = mapped.source_photo_urls[0] if mapped.source_photo_urls else None
    return store_avby_listing_photos(mapped.avby_id, cover_http, raw_from_source or None)


def _apply_mapped(
    listing: CarListing,
    mapped,
    *,
    seller_id: int,
    cover: str | None,
    raw_photos: list[dict] | None,
    scrape_row: dict[str, Any] | None = None,
    bulk_first_seen=None,
) -> None:
    listing.seller_id = seller_id
    listing.source = LISTING_SOURCE
    listing.avby_id = mapped.avby_id
    listing.external_id = mapped.external_id
    listing.title = mapped.title
    listing.brand = mapped.brand or ""
    listing.model = mapped.model or ""
    listing.generation = mapped.generation
    listing.year = int(mapped.year or 0)
    listing.mileage = int(mapped.mileage or 0)
    listing.city = (mapped.city or "Не указан")[:80]
    listing.body_type = mapped.body_type
    listing.drive_type = mapped.drive_type
    listing.engine_type = mapped.engine_type
    listing.transmission_type = mapped.transmission_type
    listing.engine_capacity_l = mapped.engine_capacity_l
    listing.engine_power_hp = mapped.engine_power_hp
    listing.source_url = mapped.source_url
    listing.cover_photo_url = cover
    listing.raw_photos = raw_photos
    listing.seller_name = mapped.seller_name
    listing.organization_id = mapped.organization_id
    listing.vin_indicated = bool(mapped.vin_indicated)
    listing.description = mapped.description or ""
    price_byn = float(mapped.price_byn) if mapped.price_byn is not None else None
    apply_import_byn_price_state(
        listing,
        price_byn=price_byn,
        price_byn_missing=mapped.price_byn_missing,
    )
    # apply_import_byn_price_state only auto-publishes when leaving price_byn_missing=True;
    # new rows default to False, so set status explicitly (same as auto24/autoplius importers).
    if mapped.price_byn_missing or price_byn is None:
        listing.status = ListingStatus.draft
    elif listing.status != ListingStatus.archived:
        listing.status = ListingStatus.published
    if mapped.avby_published_at is not None:
        listing.avby_published_at = mapped.avby_published_at
    if mapped.avby_renewed_at is not None:
        listing.avby_renewed_at = mapped.avby_renewed_at
    elif scrape_row is not None:
        apply_scrape_source_timestamps(listing, scrape_row, bulk_first_seen=bulk_first_seen)


def _archive_non_catalog(brand_to_models: dict[str, set[str]], *, dry_run: bool) -> int:
    db = SessionLocal()
    try:
        archived = 0
        rows = (
            db.query(CarListing)
            .filter(
                CarListing.avby_id.isnot(None),
                CarListing.status == ListingStatus.published,
                CarListing.organization_id.is_(None),
            )
            .all()
        )
        for listing in rows:
            if _is_in_catalog(_normalize_name(listing.brand), _model_match_key(listing.model), brand_to_models):
                continue
            archived += 1
            if not dry_run:
                listing.status = ListingStatus.archived
        if archived and not dry_run:
            db.commit()
        return archived
    finally:
        db.close()


def _archive_wrong_generation(
    catalog_generation_index: dict[tuple[str, str], tuple[frozenset[str], bool]],
    *,
    dry_run: bool,
) -> int:
    db = SessionLocal()
    try:
        archived = 0
        rows = (
            db.query(CarListing)
            .filter(
                CarListing.avby_id.isnot(None),
                CarListing.status == ListingStatus.published,
                CarListing.organization_id.is_(None),
            )
            .all()
        )
        for listing in rows:
            key = (_normalize_name(listing.brand), _model_match_key(listing.model))
            catalog_generations, catalog_allows_unrated = catalog_generation_index.get(
                key,
                (frozenset(), False),
            )
            if not catalog_generations and not catalog_allows_unrated:
                continue
            if listing_generation_allowed_for_model(
                listing.generation,
                catalog_generations=catalog_generations,
                catalog_allows_unrated=catalog_allows_unrated,
            ):
                continue
            archived += 1
            if not dry_run:
                listing.status = ListingStatus.archived
        if archived and not dry_run:
            db.commit()
        return archived
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import av.by listings from scrape Postgres")
    parser.add_argument("--dsn", default=os.getenv("AUTOPLIUS_SCRAPE_DSN") or settings.autoplius_scrape_dsn)
    parser.add_argument("--limit", type=int, default=0, help="0 = all active candidates")
    parser.add_argument("--max-hp", type=int, default=DEFAULT_MAX_HP)
    parser.add_argument("--year-min", type=int, default=DEFAULT_YEAR_MIN)
    parser.add_argument("--price-usd-min", type=int, default=DEFAULT_PRICE_USD_MIN)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-create", action="store_true")
    parser.add_argument("--no-update", action="store_true")
    parser.add_argument(
        "--archive-missing-from-scrape",
        action="store_true",
        help="Archive av.by listings absent from active scrape rows "
        "(unsafe while scrape uses creation_date incremental window; prefer avby-archive)",
    )
    parser.add_argument("--no-prune-non-catalog", action="store_true")
    parser.add_argument("--archive-overpowered", action="store_true")
    parser.add_argument("--trigger", default="manual")
    parser.add_argument("--vin-metadata-limit", type=int, default=100)
    parser.add_argument("--vin-enrich-limit", type=int, default=20)
    args = parser.parse_args()

    catalog_rows = _collect_visible_catalog_rows()
    catalog_brand_models = _collect_catalog_brand_models(catalog_rows)
    if not catalog_brand_models:
        print("No target models found in catalog_items.")
        return 1

    conn = psycopg2.connect(args.dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SELECT_SQL, (SCRAPE_SOURCE,))
            rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
    bulk_first_seen = detect_bulk_first_seen(rows)
    print(f"fetched={len(rows)} catalog_brands={len(catalog_brand_models)} bulk_first_seen_keys={len(bulk_first_seen)}")

    db = SessionLocal()
    created = updated = skipped = archived = 0
    skipped_by_catalog = skipped_by_generation = skipped_by_hp = 0
    imported_without_byn = 0
    skip_reasons: dict[str, int] = {}
    active_avby_ids: set[int] = set()
    touched: dict[int, CarListing] = {}
    run = None
    try:
        seller = _ensure_importer_user(db)
        run = _start_sync_run(db, trigger=args.trigger, max_hp=args.max_hp, dry_run=args.dry_run)
        existing_map = _load_existing_avby_map(db)
        catalog_generation_index = _build_generation_index(catalog_rows)
        rating_one_targets = build_rating_one_targets(db) if args.vin_enrich_limit != 0 else set()

        for row in rows:
            mapped = map_avby_scrape_row(
                dict(row),
                max_hp=args.max_hp,
                year_min=args.year_min,
                price_usd_min=args.price_usd_min,
                require_detail=True,
                use_app_proxy=True,
            )
            if mapped.skip_reason:
                skipped += 1
                skip_reasons[mapped.skip_reason] = skip_reasons.get(mapped.skip_reason, 0) + 1
                if mapped.skip_reason == "hp_above_max":
                    skipped_by_hp += 1
                    existing = existing_map.get(mapped.avby_id)
                    if (
                        args.archive_overpowered
                        and existing
                        and existing.status == ListingStatus.published
                        and not _is_business_org_listing(existing)
                        and not args.dry_run
                    ):
                        existing.status = ListingStatus.archived
                        archived += 1
                continue

            brand_n = _normalize_name(mapped.brand)
            model_n = _model_match_key(mapped.model)
            if not _is_in_catalog(brand_n, model_n, catalog_brand_models):
                skipped += 1
                skipped_by_catalog += 1
                skip_reasons["not_in_catalog"] = skip_reasons.get("not_in_catalog", 0) + 1
                continue

            catalog_generations, catalog_allows_unrated = catalog_generation_index.get(
                (brand_n, model_n),
                (frozenset(), False),
            )
            if not listing_generation_allowed_for_model(
                mapped.generation,
                catalog_generations=catalog_generations,
                catalog_allows_unrated=catalog_allows_unrated,
            ):
                skipped += 1
                skipped_by_generation += 1
                skip_reasons["generation_not_allowed"] = skip_reasons.get("generation_not_allowed", 0) + 1
                continue

            payload = {
                "brand": mapped.brand,
                "model": mapped.model,
                "engine_type": mapped.engine_type,
                "engine_capacity_l": mapped.engine_capacity_l,
                "engine_power_hp": mapped.engine_power_hp,
                "year": mapped.year,
            }
            if listing_payload_is_util_sbor_exclusion(payload):
                skipped += 1
                skip_reasons["util_sbor_exclusion"] = skip_reasons.get("util_sbor_exclusion", 0) + 1
                existing = existing_map.get(mapped.avby_id)
                if (
                    existing
                    and existing.status == ListingStatus.published
                    and not _is_business_org_listing(existing)
                    and not args.dry_run
                ):
                    existing.status = ListingStatus.archived
                    archived += 1
                continue

            if is_hidden_body_type(mapped.body_type):
                skipped += 1
                skip_reasons["hidden_body_type"] = skip_reasons.get("hidden_body_type", 0) + 1
                existing = existing_map.get(mapped.avby_id)
                if (
                    existing
                    and existing.status == ListingStatus.published
                    and not _is_business_org_listing(existing)
                    and not args.dry_run
                ):
                    existing.status = ListingStatus.archived
                    existing.body_type = mapped.body_type
                    archived += 1
                continue

            active_avby_ids.add(mapped.avby_id)
            existing = existing_map.get(mapped.avby_id)

            if existing is None:
                if args.no_create:
                    skipped += 1
                    skip_reasons["create_disabled"] = skip_reasons.get("create_disabled", 0) + 1
                    continue
                if args.dry_run:
                    created += 1
                    if mapped.price_byn_missing:
                        imported_without_byn += 1
                    continue
                cover, raw_photos = _resolve_photos(mapped, None)
                listing = CarListing(
                    seller_id=seller.id,
                    title=mapped.title,
                    brand=mapped.brand or "",
                    model=mapped.model or "",
                    year=int(mapped.year or 0),
                    mileage=int(mapped.mileage or 0),
                    city=(mapped.city or "Не указан")[:80],
                    description="",
                    status=ListingStatus.draft,
                )
                _apply_mapped(
                    listing,
                    mapped,
                    seller_id=seller.id,
                    cover=cover,
                    raw_photos=raw_photos,
                    scrape_row=row,
                    bulk_first_seen=bulk_first_seen,
                )
                db.add(listing)
                db.flush()
                link_listing_to_catalog(db, listing)
                existing_map[mapped.avby_id] = listing
                touched[mapped.avby_id] = listing
                created += 1
                if mapped.price_byn_missing:
                    imported_without_byn += 1
            else:
                if args.no_update:
                    skipped += 1
                    skip_reasons["update_disabled"] = skip_reasons.get("update_disabled", 0) + 1
                    continue
                if args.dry_run:
                    updated += 1
                    continue
                cover, raw_photos = _resolve_photos(mapped, existing)
                # Preserve VIN fields
                preserved = {f: getattr(existing, f, None) for f in PRESERVE_ON_UPDATE_FIELDS}
                _apply_mapped(
                    existing,
                    mapped,
                    seller_id=seller.id,
                    cover=cover,
                    raw_photos=raw_photos,
                    scrape_row=row,
                    bulk_first_seen=bulk_first_seen,
                )
                for field, value in preserved.items():
                    if value is not None:
                        setattr(existing, field, value)
                link_listing_to_catalog(db, existing)
                touched[mapped.avby_id] = existing
                updated += 1
                if mapped.price_byn_missing:
                    imported_without_byn += 1

        archived_non_catalog = 0
        archived_wrong_generation = 0
        if not args.no_prune_non_catalog:
            archived_non_catalog = _archive_non_catalog(catalog_brand_models, dry_run=args.dry_run)
            archived_wrong_generation = _archive_wrong_generation(
                catalog_generation_index,
                dry_run=args.dry_run,
            )
            archived += archived_non_catalog + archived_wrong_generation

        if args.archive_missing_from_scrape and not args.dry_run and not (args.limit and args.limit > 0):
            for avby_id, listing in existing_map.items():
                if avby_id in active_avby_ids:
                    continue
                if _is_business_org_listing(listing):
                    continue
                if listing.status == ListingStatus.archived:
                    continue
                listing.status = ListingStatus.archived
                archived += 1
        elif args.archive_missing_from_scrape and args.limit and args.limit > 0:
            print("archive_missing_from_scrape skipped because --limit is set")

        if not args.dry_run and touched:
            for listing in touched.values():
                link_listing_to_catalog(db, listing)
            db.commit()

        if not args.dry_run and args.vin_metadata_limit != 0 and touched:
            metadata_stats = enrich_listings_vin_metadata(
                db,
                list(touched.values()),
                limit=args.vin_metadata_limit if args.vin_metadata_limit > 0 else None,
                sync_run_id=run.id if run else None,
            )
            print(
                "enrich-vin-metadata: "
                f"eligible={metadata_stats.eligible} attempted={metadata_stats.attempted} "
                f"fetched={metadata_stats.fetched} vin_saved={metadata_stats.vin_saved}"
            )

        if not args.dry_run and args.vin_enrich_limit != 0 and touched:
            enrich_stats = enrich_rating_one_listings(
                db,
                list(touched.values()),
                targets=rating_one_targets,
                limit=args.vin_enrich_limit if args.vin_enrich_limit > 0 else None,
                sync_run_id=run.id if run else None,
            )
            print(
                "enrich-rating-1: "
                f"eligible={enrich_stats.eligible} attempted={enrich_stats.attempted} "
                f"vin_fetched={enrich_stats.vin_fetched}"
            )

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        status = "success"
        _finish_sync_run(
            db,
            run,
            status=status,
            models_count=sum(len(v) for v in catalog_brand_models.values()),
            brands_count=len(catalog_brand_models),
            created=created,
            updated=updated,
            skipped=skipped,
            skipped_by_hp=skipped_by_hp,
            pages_fetched=len(rows),
        )
    except Exception as exc:
        if args.dry_run:
            db.rollback()
        _finish_sync_run(
            db,
            run,
            status="failed",
            models_count=sum(len(v) for v in catalog_brand_models.values()),
            brands_count=len(catalog_brand_models),
            created=created,
            updated=updated,
            skipped=skipped,
            skipped_by_hp=skipped_by_hp,
            pages_fetched=len(rows),
            error_message=str(exc),
        )
        raise
    finally:
        db.close()

    print(
        f"done dry_run={args.dry_run} created={created} updated={updated} "
        f"skipped={skipped} archived={archived} "
        f"skipped_by_catalog={skipped_by_catalog} skipped_by_generation={skipped_by_generation} "
        f"skipped_by_hp={skipped_by_hp} imported_without_byn={imported_without_byn}"
    )
    if skip_reasons:
        print("skip_reasons:")
        for reason, count in sorted(skip_reasons.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {reason}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
