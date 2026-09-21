#!/usr/bin/env python3
"""Import all active av.by listings for known business sellers (no ≤160 filter).

Only companies already present in Auto160 as legal-entity seller_name are synced.
Listings with engine_power_hp > 160 (or missing) are stored as draft (admin
business-sellers only). Matching ≤160 go published (same as public feed).

Closed historical ads are not available via the public filter API; use
archive_removed_avby_listings.py for ads we already know that leave av.by.

Examples:

  python tools/import_avby_business_listings.py --since 2026-01-01
  python tools/import_avby_business_listings.py --dry-run --limit-orgs 3
  python tools/import_avby_business_listings.py --seller-name 'ООО'
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from curl_cffi import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from sqlalchemy import or_

from app.avby_photo_store import is_avby_s3_media_url, store_avby_listing_photos
from app.db import SessionLocal
from app.listing_display import is_legal_entity_seller
from app.listing_missing_byn import apply_import_byn_price_state
from app.logging_setup import setup_logging
from app.models import CarListing, ListingStatus, User
from app.seller_analytics import normalize_seller_key

# Load sibling importer module (tools/ is not a package).
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "import_avby_listings",
    ROOT_DIR / "tools" / "import_avby_listings.py",
)
_avby = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_avby)

APPLY_URL = _avby.APPLY_URL
FILTER_REFERER = _avby.FILTER_REFERER
INIT_URL = _avby.INIT_URL
PRESERVE_ON_UPDATE_FIELDS = _avby.PRESERVE_ON_UPDATE_FIELDS
_avby_payload_to_listing = _avby._avby_payload_to_listing
_ensure_importer_user = _avby._ensure_importer_user
_load_existing_avby_map = _avby._load_existing_avby_map
_parse_avby_datetime = _avby._parse_avby_datetime
_to_int = _avby._to_int

import logging

logger = logging.getLogger(__name__)

DEFAULT_SINCE = "2026-01-01"
DEFAULT_MAX_HP_PUBLIC = 160
DEFAULT_SORT = 4  # newest first (same as main sync)
REQUEST_PAUSE_SEC = 0.35


def _parse_since(value: str) -> datetime:
    raw = (value or "").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"Invalid --since date: {value!r} (use YYYY-MM-DD)")


def _as_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _fetch_json(method: str, url: str, *, user_agent: str, payload: dict | None = None) -> dict[str, Any]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "x-device-type": "web.desktop",
        "Origin": "https://av.by",
        "Referer": FILTER_REFERER,
    }
    last_exc: Exception | None = None
    for attempt in range(1, 4):
        try:
            if method == "GET":
                response = requests.get(url, impersonate="chrome124", timeout=45, headers=headers)
            else:
                response = requests.post(
                    url, impersonate="chrome124", timeout=45, headers=headers, json=payload or {}
                )
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * attempt)
                continue
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(1.5 * attempt)
    assert last_exc is not None
    raise last_exc


def fetch_organization_options(user_agent: str) -> list[tuple[int, str]]:
    data = _fetch_json("GET", INIT_URL, user_agent=user_agent)
    options: list[tuple[int, str]] = []
    for block in data.get("blocks") or []:
        for row in block.get("rows") or []:
            for group in row.get("propertyGroups") or []:
                for prop in group.get("properties") or []:
                    if prop.get("name") != "organization":
                        continue
                    for opt in prop.get("options") or []:
                        org_id = _to_int(opt.get("id") or opt.get("intValue"))
                        label = (opt.get("label") or "").strip()
                        if org_id is None or not label:
                            continue
                        options.append((org_id, label))
    return options


def load_known_business_sellers(db) -> dict[str, str]:
    """normalized_key -> display seller_name for legal-entity sellers already in DB."""
    rows = (
        db.query(CarListing.seller_name)
        .filter(
            CarListing.seller_name.isnot(None),
            CarListing.seller_name != "",
            or_(CarListing.source.is_(None), CarListing.source == "av.by"),
        )
        .distinct()
        .all()
    )
    result: dict[str, str] = {}
    for (raw,) in rows:
        name = (raw or "").strip()
        if not is_legal_entity_seller(name):
            continue
        key = normalize_seller_key(name)
        prev = result.get(key)
        if prev is None or len(name) > len(prev):
            result[key] = name
    return result


def load_org_ids_from_listings(db) -> dict[str, int]:
    """normalized seller_name -> organization_id from rows that already have it."""
    rows = (
        db.query(CarListing.seller_name, CarListing.organization_id)
        .filter(
            CarListing.organization_id.isnot(None),
            CarListing.seller_name.isnot(None),
            CarListing.seller_name != "",
        )
        .all()
    )
    mapped: dict[str, int] = {}
    for seller_name, org_id in rows:
        if org_id is None:
            continue
        name = (seller_name or "").strip()
        if not name:
            continue
        mapped[normalize_seller_key(name)] = int(org_id)
    return mapped


def match_organizations(
    known_sellers: dict[str, str],
    org_options: list[tuple[int, str]],
    known_org_ids: dict[str, int],
) -> tuple[list[tuple[int, str, str]], list[str]]:
    """Return (matched: org_id, org_label, seller_display), unmatched seller display names."""
    option_by_key: dict[str, tuple[int, str]] = {}
    for org_id, label in org_options:
        option_by_key[normalize_seller_key(label)] = (org_id, label)

    matched: list[tuple[int, str, str]] = []
    unmatched: list[str] = []
    used_orgs: set[int] = set()

    for key, display in sorted(known_sellers.items(), key=lambda item: item[1].casefold()):
        org_id = known_org_ids.get(key)
        org_label = display
        if org_id is None:
            hit = option_by_key.get(key)
            if hit is None:
                unmatched.append(display)
                continue
            org_id, org_label = hit
        if org_id in used_orgs:
            continue
        used_orgs.add(org_id)
        matched.append((org_id, org_label, display))

    return matched, unmatched


def fetch_org_adverts(
    org_id: int,
    *,
    user_agent: str,
    since: datetime,
    sort: int = DEFAULT_SORT,
) -> list[dict[str, Any]]:
    since_naive = _as_naive(since) or since
    collected: list[dict[str, Any]] = []
    page = 1
    page_count = 1
    while page <= page_count:
        payload = {
            "page": page,
            "sorting": sort,
            "properties": [{"name": "organization", "value": org_id}],
        }
        data = _fetch_json("POST", APPLY_URL, user_agent=user_agent, payload=payload)
        page_count = int(data.get("pageCount") or 1)
        adverts = data.get("adverts") or []
        if not adverts:
            break
        stop_early = False
        for advert in adverts:
            published = _as_naive(_parse_avby_datetime(advert.get("publishedAt")))
            if published is not None and published < since_naive:
                # sort=4 is newest-first → older pages only get older
                if sort == 4:
                    stop_early = True
                continue
            collected.append(advert)
        if stop_early:
            break
        page += 1
        time.sleep(REQUEST_PAUSE_SEC)
    return collected


def _target_status(payload: dict[str, Any], *, price_byn_missing: bool) -> ListingStatus:
    hp = payload.get("engine_power_hp")
    if hp is None or int(hp) > DEFAULT_MAX_HP_PUBLIC:
        return ListingStatus.draft
    if price_byn_missing:
        return ListingStatus.draft
    return ListingStatus.published


def upsert_advert(
    db,
    advert: dict[str, Any],
    *,
    seller: User,
    existing_map: dict[int, CarListing],
    dry_run: bool,
) -> str:
    """Return 'created' | 'updated' | 'skipped'."""
    org_title = (advert.get("organizationTitle") or advert.get("sellerName") or "").strip()
    meta = advert.get("metadata") or {}
    fallback_brand = str(meta.get("brandSlug") or "").replace("-", " ").strip()
    fallback_model = str(meta.get("modelSlug") or "").replace("-", " ").strip()
    payload = _avby_payload_to_listing(
        advert,
        fallback_brand=fallback_brand,
        fallback_model=fallback_model,
    )
    if payload is None:
        return "skipped"

    avby_id = payload.pop("avby_id")
    price_byn_missing = bool(payload.pop("price_byn_missing", False))
    price_byn = payload.get("price")
    if not payload.get("seller_name") and org_title:
        payload["seller_name"] = org_title[:120]

    status = _target_status(payload, price_byn_missing=price_byn_missing)
    existing = existing_map.get(avby_id)

    if dry_run:
        return "updated" if existing else "created"

    if existing:
        if is_avby_s3_media_url(existing.cover_photo_url) and isinstance(existing.raw_photos, list) and existing.raw_photos:
            payload["cover_photo_url"] = existing.cover_photo_url
            payload["raw_photos"] = existing.raw_photos
        else:
            cover, raw_photos = store_avby_listing_photos(
                avby_id,
                payload.get("cover_photo_url"),
                payload.get("raw_photos"),
            )
            payload["cover_photo_url"] = cover
            payload["raw_photos"] = raw_photos

        existing.avby_id = avby_id
        existing.source = "av.by"
        existing.external_id = str(avby_id)
        for field, value in payload.items():
            if field in PRESERVE_ON_UPDATE_FIELDS:
                continue
            setattr(existing, field, value)
        apply_import_byn_price_state(
            existing,
            price_byn=price_byn,
            price_byn_missing=price_byn_missing,
        )
        # Active on av.by → refresh public/draft visibility from HP rules.
        existing.status = status
        existing_map[avby_id] = existing
        return "updated"

    cover, raw_photos = store_avby_listing_photos(
        avby_id,
        payload.get("cover_photo_url"),
        payload.get("raw_photos"),
    )
    payload["cover_photo_url"] = cover
    payload["raw_photos"] = raw_photos
    listing = CarListing(
        seller_id=seller.id,
        avby_id=avby_id,
        source="av.by",
        external_id=str(avby_id),
        status=status,
        price_byn_missing=price_byn_missing,
        **payload,
    )
    db.add(listing)
    existing_map[avby_id] = listing
    return "created"


def run_import(
    *,
    since: datetime,
    user_agent: str = "Mozilla/5.0",
    dry_run: bool = False,
    limit_orgs: int = 0,
    seller_name_filter: str | None = None,
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        known = load_known_business_sellers(db)
        if seller_name_filter:
            needle = seller_name_filter.strip().casefold()
            known = {k: v for k, v in known.items() if needle in v.casefold()}

        known_org_ids = load_org_ids_from_listings(db)
        logger.info("known business sellers=%s", len(known))

        org_options = fetch_organization_options(user_agent)
        logger.info("av.by organization options=%s", len(org_options))
        matched, unmatched = match_organizations(known, org_options, known_org_ids)
        if limit_orgs > 0:
            matched = matched[:limit_orgs]

        logger.info("matched orgs=%s unmatched sellers=%s", len(matched), len(unmatched))
        for name in unmatched[:50]:
            logger.warning("unmatched business seller: %s", name)

        seller = _ensure_importer_user(db)
        existing_map = _load_existing_avby_map(db)

        created = updated = skipped = 0
        ads_seen = 0
        org_errors: list[str] = []

        for idx, (org_id, org_label, display) in enumerate(matched, start=1):
            logger.info(
                "[%s/%s] org_id=%s label=%s seller=%s",
                idx,
                len(matched),
                org_id,
                org_label,
                display,
            )
            try:
                adverts = fetch_org_adverts(org_id, user_agent=user_agent, since=since)
            except Exception as exc:  # noqa: BLE001
                logger.exception("org fetch failed org_id=%s", org_id)
                org_errors.append(f"{org_id}:{exc}")
                continue

            ads_seen += len(adverts)
            for advert in adverts:
                # Force organization id onto payload path
                if advert.get("organizationId") is None:
                    advert["organizationId"] = org_id
                if not (advert.get("sellerName") or "").strip():
                    advert["sellerName"] = display
                try:
                    result = upsert_advert(
                        db,
                        advert,
                        seller=seller,
                        existing_map=existing_map,
                        dry_run=dry_run,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("upsert failed avby_id=%s: %s", advert.get("id"), exc)
                    skipped += 1
                    continue
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                else:
                    skipped += 1

            if not dry_run:
                db.commit()
            time.sleep(REQUEST_PAUSE_SEC)

        stats = {
            "known_sellers": len(known),
            "matched_orgs": len(matched),
            "unmatched_sellers": len(unmatched),
            "unmatched_sample": unmatched[:30],
            "ads_seen": ads_seen,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "org_errors": org_errors[:20],
            "dry_run": dry_run,
            "since": since.isoformat(sep=" "),
        }
        logger.info("business-import done %s", stats)
        return stats
    finally:
        db.close()


def main() -> int:
    setup_logging("avby-business-import")
    parser = argparse.ArgumentParser(description="Import all listings for known av.by business sellers")
    parser.add_argument("--since", type=_parse_since, default=_parse_since(DEFAULT_SINCE))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-orgs", type=int, default=0, help="Cap number of organizations (0=all)")
    parser.add_argument("--seller-name", type=str, default=None, help="Substring filter on seller display name")
    parser.add_argument("--user-agent", type=str, default="Mozilla/5.0")
    args = parser.parse_args()

    stats = run_import(
        since=args.since,
        user_agent=args.user_agent,
        dry_run=args.dry_run,
        limit_orgs=args.limit_orgs,
        seller_name_filter=args.seller_name,
    )
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
