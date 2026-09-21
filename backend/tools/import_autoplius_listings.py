#!/usr/bin/env python3
"""Import Autoplius listings from scrape Postgres into Auto160 car_listings.

Example:

  python tools/import_autoplius_listings.py --dry-run --limit 20
  python tools/import_autoplius_listings.py --limit 50
  python tools/import_autoplius_listings.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.autoplius_map import (
    DEFAULT_MAX_AGE_YEARS,
    DEFAULT_MAX_ENGINE_L,
    fetch_eur_rate,
    map_autoplius_row,
)
from app.body_type_labels import is_hidden_body_type
from app.config import settings
from app.db import SessionLocal
from app.listing_catalog_link import link_listing_to_catalog
from app.listing_missing_byn import apply_import_byn_price_state
from app.models import CarListing, ListingStatus, User, UserRole
from app.security import hash_password

SOURCE = "autoplius"

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
  status
FROM listings
WHERE source = %s
  AND status = 'active'
ORDER BY id DESC
"""


def _ensure_importer_user(db) -> User:
    existing = db.query(User).filter(User.username == "autoplius_importer").first()
    if existing:
        return existing
    user = User(
        username="autoplius_importer",
        email="autoplius_importer@auto160.local",
        name="Autoplius Importer",
        role=UserRole.seller,
        password_hash=hash_password("change_me_now_123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _photo_payload(mapped) -> tuple[str | None, list[dict] | None]:
    keys = list(mapped.photo_storage_keys or [])
    cover = mapped.cover_photo_url
    raw_photos = [{"url": url} for url in (mapped.photo_urls or []) if url]
    return cover, raw_photos or None


def _apply_mapped(listing: CarListing, mapped, *, seller_id: int) -> None:
    cover, raw_photos = _photo_payload(mapped)
    listing.seller_id = seller_id
    listing.source = SOURCE
    listing.external_id = mapped.external_id
    listing.title = mapped.title
    listing.brand = mapped.brand or ""
    listing.model = mapped.model or ""
    listing.year = int(mapped.year or 0)
    listing.mileage = int(mapped.mileage or 0)
    listing.city = (mapped.city or "Литва")[:80]
    listing.body_type = mapped.body_type
    listing.engine_type = mapped.engine_type
    listing.transmission_type = mapped.transmission_type
    listing.engine_capacity_l = mapped.engine_capacity_l
    listing.engine_power_hp = mapped.engine_power_hp
    listing.source_url = mapped.source_url
    listing.cover_photo_url = cover
    listing.raw_photos = raw_photos
    listing.seller_name = None
    listing.vin_indicated = bool(mapped.vin_masked)
    description = mapped.description or ""
    listing.description = (
        f"{description}\n\n"
        f"Источник: autoplius.lt\n"
        f"URL: {mapped.source_url or ''}\n"
        f"AUTOPLIUS_ID: {mapped.external_id}"
    ).strip()
    price_byn = float(mapped.price_byn) if mapped.price_byn is not None else None
    price_missing = price_byn is None
    apply_import_byn_price_state(listing, price_byn=price_byn, price_byn_missing=price_missing)
    listing.status = ListingStatus.draft if price_missing else ListingStatus.published


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Autoplius listings into Auto160")
    parser.add_argument("--dsn", default=os.getenv("AUTOPLIUS_SCRAPE_DSN") or settings.autoplius_scrape_dsn)
    parser.add_argument("--limit", type=int, default=0, help="0 = all active candidates")
    parser.add_argument("--max-hp", type=int, default=160)
    parser.add_argument(
        "--max-age-years",
        type=int,
        default=DEFAULT_MAX_AGE_YEARS,
        help="Keep cars with age ≤ N years (manufacture year ≥ current-N)",
    )
    parser.add_argument(
        "--max-engine-l",
        type=float,
        default=DEFAULT_MAX_ENGINE_L,
        help="Keep cars with engine capacity ≤ N liters",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-create", action="store_true", help="Do not create new rows")
    parser.add_argument("--no-update", action="store_true", help="Do not update existing rows")
    parser.add_argument("--skip-archive-sync", action="store_true")
    args = parser.parse_args()

    eur = fetch_eur_rate()
    if eur:
        print(f"nbrb_eur rate={eur.rate} scale={eur.scale} date={eur.rate_date.isoformat()}")
    else:
        print("nbrb_eur UNAVAILABLE")

    conn = psycopg2.connect(args.dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(SELECT_SQL, (SOURCE,))
            rows = cur.fetchall()
    finally:
        conn.close()

    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
    print(f"fetched={len(rows)}")

    db = SessionLocal()
    created = updated = skipped = archived = 0
    skip_reasons: dict[str, int] = {}
    active_external_ids: set[str] = set()
    try:
        seller = _ensure_importer_user(db)
        existing_rows = (
            db.query(CarListing)
            .filter(CarListing.source == SOURCE)
            .all()
        )
        by_external = {row.external_id: row for row in existing_rows if row.external_id}

        for row in rows:
            mapped = map_autoplius_row(
                dict(row),
                eur_rate=eur,
                max_hp=args.max_hp,
                max_age_years=args.max_age_years,
                max_engine_l=args.max_engine_l,
                require_detail=True,
                use_app_proxy=True,
            )
            if mapped.skip_reason:
                skipped += 1
                skip_reasons[mapped.skip_reason] = skip_reasons.get(mapped.skip_reason, 0) + 1
                continue
            if is_hidden_body_type(mapped.body_type):
                skipped += 1
                skip_reasons["hidden_body_type"] = skip_reasons.get("hidden_body_type", 0) + 1
                continue
            if (row.get("status") or "").strip() != "active":
                skipped += 1
                skip_reasons["not_active"] = skip_reasons.get("not_active", 0) + 1
                continue

            active_external_ids.add(mapped.external_id)
            existing = by_external.get(mapped.external_id)
            if existing is None:
                if args.no_create:
                    skipped += 1
                    skip_reasons["create_disabled"] = skip_reasons.get("create_disabled", 0) + 1
                    continue
                if args.dry_run:
                    created += 1
                    continue
                listing = CarListing(
                    seller_id=seller.id,
                    title=mapped.title,
                    brand=mapped.brand or "",
                    model=mapped.model or "",
                    year=int(mapped.year or 0),
                    mileage=int(mapped.mileage or 0),
                    city=(mapped.city or "Литва")[:80],
                    description="",
                    status=ListingStatus.draft,
                )
                _apply_mapped(listing, mapped, seller_id=seller.id)
                db.add(listing)
                db.flush()
                link_listing_to_catalog(db, listing)
                by_external[mapped.external_id] = listing
                created += 1
            else:
                if args.no_update:
                    skipped += 1
                    skip_reasons["update_disabled"] = skip_reasons.get("update_disabled", 0) + 1
                    continue
                if args.dry_run:
                    updated += 1
                    continue
                _apply_mapped(existing, mapped, seller_id=seller.id)
                link_listing_to_catalog(db, existing)
                updated += 1

        if not args.skip_archive_sync and not args.dry_run and not (args.limit and args.limit > 0):
            for ext_id, listing in by_external.items():
                if ext_id in active_external_ids:
                    continue
                if listing.status == ListingStatus.archived:
                    continue
                listing.status = ListingStatus.archived
                archived += 1
        elif args.limit and args.limit > 0 and not args.skip_archive_sync:
            print("archive_sync skipped because --limit is set")

        if not args.dry_run:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()

    print(
        f"done dry_run={args.dry_run} created={created} updated={updated} "
        f"skipped={skipped} archived={archived}"
    )
    if skip_reasons:
        print("skip_reasons:")
        for reason, count in sorted(skip_reasons.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {reason}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
