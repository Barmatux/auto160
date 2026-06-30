import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from curl_cffi import requests

# Allow running script directly: `python tools/import_avby_listings.py ...`
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.models import AvbySyncRun, CarListing, CatalogItem, ListingStatus, User, UserRole
from app.security import hash_password


AVBY_ID_RE = re.compile(r"AVBY_ID:\s*(\d+)")
APPLY_URL = "https://web-api.av.by/offer-types/cars/filters/main/apply"
INIT_URL = "https://web-api.av.by/offer-types/cars/filters/main/init"


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d]", "", str(value))
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    cleaned = str(value).strip().replace(",", ".")
    cleaned = re.sub(r"[^0-9.]", "", cleaned)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "да"}:
        return True
    if normalized in {"0", "false", "no", "нет"}:
        return False
    return None


def _ensure_importer_user(db) -> User:
    user = db.query(User).filter(User.role == UserRole.admin).order_by(User.id.asc()).first()
    if user:
        return user
    user = db.query(User).order_by(User.id.asc()).first()
    if user:
        return user

    base_username = "avby_importer"
    username = base_username
    suffix = 1
    while db.query(User.id).filter(User.username == username).first():
        username = f"{base_username}_{suffix}"
        suffix += 1

    email = f"{username}@auto160.local"
    created = User(
        username=username,
        email=email,
        name="AV.BY Importer",
        role=UserRole.seller,
        password_hash=hash_password("change_me_now_123"),
    )
    db.add(created)
    db.commit()
    db.refresh(created)
    return created


def _normalize_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9]+", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _collect_target_models(
    make_filter: str | None,
    model_filter: str | None,
    limit_models: int | None,
) -> list[tuple[str, str]]:
    db = SessionLocal()
    try:
        query = db.query(CatalogItem).filter(CatalogItem.source_site == "av.by", CatalogItem.source_url.isnot(None))
        if make_filter:
            query = query.filter(CatalogItem.make.ilike(f"%{make_filter}%"))
        if model_filter:
            query = query.filter(CatalogItem.model.ilike(f"%{model_filter}%"))

        rows = query.order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.id.desc()).all()
        pairs: dict[tuple[str, str], tuple[str, str]] = {}
        for item in rows:
            make = (item.make or "").strip()
            model = (item.model or "").strip()
            if not make or not model:
                continue
            key = (_normalize_name(make), _normalize_name(model))
            if key in pairs:
                continue
            pairs[key] = (make, model)

        result = list(pairs.values())
        if limit_models is not None:
            result = result[:limit_models]
        return result
    finally:
        db.close()


def _extract_properties_map(advert: dict[str, Any]) -> dict[str, Any]:
    props_map: dict[str, Any] = {}
    for prop in advert.get("properties") or []:
        name = prop.get("name")
        if not name:
            continue
        props_map[name] = prop.get("value")
    return props_map


def _extract_photo_urls(advert: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    photos = advert.get("photos") or []
    normalized_photos: list[dict[str, Any]] = []
    cover_url = None
    for photo in photos:
        if not isinstance(photo, dict):
            continue
        variants = {}
        for variant_name in ("big", "medium", "small", "extrasmall"):
            variant = photo.get(variant_name)
            if isinstance(variant, dict) and variant.get("url"):
                variants[variant_name] = variant.get("url")
        normalized_photos.append(
            {
                "id": photo.get("id"),
                "main": bool(photo.get("main")),
                "mimeType": photo.get("mimeType"),
                "variants": variants,
            }
        )
        if cover_url is None and variants:
            if photo.get("main"):
                cover_url = variants.get("big") or variants.get("medium") or variants.get("small")
    if cover_url is None:
        for photo in normalized_photos:
            variants = photo.get("variants") or {}
            cover_url = variants.get("big") or variants.get("medium") or variants.get("small")
            if cover_url:
                break
    return cover_url, normalized_photos


def _avby_payload_to_listing(advert: dict[str, Any], fallback_brand: str, fallback_model: str) -> dict[str, Any] | None:
    avby_id = _to_int(advert.get("id"))
    if avby_id is None:
        return None

    props = _extract_properties_map(advert)
    brand = (props.get("brand") or fallback_brand or "").strip()
    model = (props.get("model") or fallback_model or "").strip()
    year = _to_int(advert.get("year") or props.get("year"))
    if not brand or not model or year is None:
        return None

    mileage = _to_int(props.get("mileage_km")) or 0
    price_rub = _to_float((((advert.get("price") or {}).get("rub") or {}).get("amount")))
    if price_rub is None:
        price_rub = _to_float((((advert.get("price") or {}).get("byn") or {}).get("amount")))
    if price_rub is None:
        price_rub = 0.0

    city = (advert.get("shortLocationName") or advert.get("locationName") or "Не указан").strip()
    public_url = (advert.get("publicUrl") or "").strip()
    cover_photo_url, raw_photos = _extract_photo_urls(advert)

    raw_title = (advert.get("metadata") or {}).get("title")
    if isinstance(raw_title, str) and raw_title.strip():
        title = raw_title.strip()
    else:
        title = f"{brand} {model} {year} (av.by #{avby_id})"

    body = (advert.get("description") or "").strip()
    description = (
        f"{body}\n\n"
        f"Источник: av.by\n"
        f"URL: {public_url}\n"
        f"AVBY_ID: {avby_id}"
    ).strip()

    return {
        "avby_id": avby_id,
        "title": title[:180],
        "brand": brand[:80],
        "model": model[:80],
        "generation": str(props.get("generation") or "").strip()[:120] or None,
        "year": year,
        "mileage": mileage,
        "price": price_rub,
        "city": city[:80],
        "body_type": str(props.get("body_type") or "").strip()[:60] or None,
        "drive_type": str(props.get("drive_type") or "").strip()[:40] or None,
        "transmission_type": str(props.get("transmission_type") or "").strip()[:40] or None,
        "engine_type": str(props.get("engine_type") or "").strip()[:40] or None,
        "engine_capacity_l": _to_float(props.get("engine_capacity")),
        "engine_power_hp": _to_int(props.get("engine_power")),
        "vin_indicated": _to_bool(props.get("vin_indicated")),
        "seller_name": (advert.get("sellerName") or "").strip()[:120] or None,
        "source_url": public_url[:500] or None,
        "cover_photo_url": cover_photo_url[:500] if cover_photo_url else None,
        "raw_photos": raw_photos or None,
        "description": description,
    }


def _load_existing_avby_map(db) -> dict[int, CarListing]:
    rows = db.query(CarListing).all()
    mapped: dict[int, CarListing] = {}
    for row in rows:
        if row.avby_id is not None:
            mapped[row.avby_id] = row
            continue
        match = AVBY_ID_RE.search(row.description or "")
        if not match:
            continue
        avby_id = _to_int(match.group(1))
        if avby_id is None:
            continue
        mapped[avby_id] = row
    return mapped


def _fetch_brand_id_map(user_agent: str) -> dict[str, int]:
    response = requests.get(
        INIT_URL,
        impersonate="chrome124",
        timeout=30,
        headers={
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://av.by/",
        },
    )
    response.raise_for_status()
    data = response.json()
    blocks = data.get("blocks") or []

    brand_options: list[dict[str, Any]] = []
    for block in blocks:
        for row in block.get("rows") or []:
            for group in row.get("propertyGroups") or []:
                for prop in group.get("properties") or []:
                    if prop.get("name") == "brands":
                        variants = prop.get("value") or []
                        for variant in variants:
                            for nested in variant:
                                if nested.get("name") == "brand":
                                    brand_options = nested.get("options") or []
                                    break
                            if brand_options:
                                break
                    if brand_options:
                        break
                if brand_options:
                    break
            if brand_options:
                break
        if brand_options:
            break

    mapping: dict[str, int] = {}
    for option in brand_options:
        label = (option.get("label") or "").strip()
        option_id = _to_int(option.get("id") or option.get("intValue"))
        if not label or option_id is None:
            continue
        mapping[_normalize_name(label)] = option_id
    return mapping


def _fetch_brand_page(brand_id: int, page: int, user_agent: str) -> dict[str, Any]:
    payload = {
        "page": page,
        "sorting": 4,
        "properties": [
            {"name": "price_currency", "value": 2},
            {"name": "brands", "value": [{"brand": brand_id}]},
        ],
    }
    response = requests.post(
        APPLY_URL,
        impersonate="chrome124",
        timeout=30,
        headers={
            "User-Agent": user_agent,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "x-device-type": "web.desktop",
            "Origin": "https://av.by",
            "Referer": "https://av.by/",
        },
        json=payload,
    )
    response.raise_for_status()
    return response.json()


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
    failed_brands: int,
    pages_fetched: int,
    error_message: str | None = None,
) -> None:
    if run is None:
        return
    run.finished_at = datetime.utcnow()
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


def run_import(
    *,
    user_agent: str = "Mozilla/5.0",
    make: str | None = None,
    model: str | None = None,
    limit_models: int | None = None,
    per_model_limit: int = 30,
    max_pages: int = 30,
    max_hp: int = 160,
    update_existing: bool = True,
    archive_overpowered: bool = False,
    dry_run: bool = False,
    trigger: str = "manual",
) -> dict[str, Any]:
    targets = _collect_target_models(make, model, limit_models)
    if not targets:
        print("No target models found in catalog_items (source_site=av.by).")
        db = SessionLocal()
        try:
            run = _start_sync_run(db, trigger=trigger, max_hp=max_hp, dry_run=dry_run)
            _finish_sync_run(
                db,
                run,
                status="success",
                models_count=0,
                brands_count=0,
                created=0,
                updated=0,
                skipped=0,
                skipped_by_hp=0,
                failed_brands=0,
                pages_fetched=0,
            )
        finally:
            db.close()
        return {"status": "success", "models": 0, "brands": 0, "created": 0, "updated": 0}

    brand_to_models: dict[str, set[str]] = {}
    canonical_model_name: dict[tuple[str, str], str] = {}
    canonical_brand_name: dict[str, str] = {}
    for make_name, model_name in targets:
        make_n = _normalize_name(make_name)
        model_n = _normalize_name(model_name)
        if not make_n or not model_n:
            continue
        brand_to_models.setdefault(make_n, set()).add(model_n)
        canonical_model_name[(make_n, model_n)] = model_name
        canonical_brand_name[make_n] = make_name

    print(f"models: {len(targets)} brands: {len(brand_to_models)}")
    brand_id_map = _fetch_brand_id_map(user_agent)

    db = SessionLocal()
    run = None
    created = 0
    updated = 0
    skipped = 0
    skipped_by_hp = 0
    failed_brands = 0
    pages_fetched = 0
    try:
        run = _start_sync_run(db, trigger=trigger, max_hp=max_hp, dry_run=dry_run)
        seller = _ensure_importer_user(db)
        existing_map = _load_existing_avby_map(db)
        imported_per_model: dict[tuple[str, str], int] = {}

        for brand_n, model_set in brand_to_models.items():
            brand_id = brand_id_map.get(brand_n)
            brand_display = canonical_brand_name.get(brand_n, brand_n)
            if brand_id is None:
                failed_brands += 1
                print(f"skip-brand: {brand_display} -> brand id not found in av.by filters")
                continue

            page = 1
            page_count = max_pages
            print(f"fetch-brand: {brand_display} (id={brand_id})")
            while page <= min(page_count, max_pages):
                try:
                    page_data = _fetch_brand_page(brand_id=brand_id, page=page, user_agent=user_agent)
                except Exception as exc:
                    failed_brands += 1
                    print(f"fail-brand-page: {brand_display} page={page} -> {exc}")
                    break

                pages_fetched += 1
                page_count = _to_int(page_data.get("pageCount")) or page_count
                adverts = page_data.get("adverts") or []
                print(
                    f"  page {page}/{min(page_count, max_pages)}: "
                    f"adverts={len(adverts)}"
                )

                if not adverts:
                    break

                for advert in adverts:
                    props = _extract_properties_map(advert)
                    advert_brand = (props.get("brand") or brand_display or "").strip()
                    advert_model = (props.get("model") or "").strip()
                    advert_brand_n = _normalize_name(advert_brand)
                    advert_model_n = _normalize_name(advert_model)
                    target_key = (advert_brand_n, advert_model_n)

                    if advert_brand_n != brand_n or advert_model_n not in model_set:
                        skipped += 1
                        continue

                    if per_model_limit > 0 and imported_per_model.get(target_key, 0) >= per_model_limit:
                        skipped += 1
                        continue

                    payload = _avby_payload_to_listing(
                        advert,
                        fallback_brand=canonical_brand_name.get(brand_n, advert_brand),
                        fallback_model=canonical_model_name.get(target_key, advert_model),
                    )
                    if payload is None:
                        skipped += 1
                        continue
                    avby_id = payload.pop("avby_id")
                    power_hp = _to_int(payload.get("engine_power_hp"))
                    existing = existing_map.get(avby_id)

                    if power_hp is None or power_hp > max_hp:
                        skipped += 1
                        skipped_by_hp += 1
                        if archive_overpowered and existing:
                            existing.status = ListingStatus.archived
                        continue

                    if existing:
                        if not update_existing:
                            skipped += 1
                            continue
                        existing.avby_id = avby_id
                        for field, value in payload.items():
                            setattr(existing, field, value)
                        existing.status = ListingStatus.published
                        updated += 1
                        imported_per_model[target_key] = imported_per_model.get(target_key, 0) + 1
                        continue

                    listing = CarListing(
                        seller_id=seller.id,
                        avby_id=avby_id,
                        status=ListingStatus.published,
                        **payload,
                    )
                    db.add(listing)
                    existing_map[avby_id] = listing
                    created += 1
                    imported_per_model[target_key] = imported_per_model.get(target_key, 0) + 1

                if not dry_run:
                    db.commit()

                if per_model_limit > 0 and all(
                    imported_per_model.get((brand_n, m), 0) >= per_model_limit for m in model_set
                ):
                    print(f"  stop-brand: reached per-model limit for all target models ({len(model_set)})")
                    break
                page += 1

        if dry_run:
            db.rollback()

        status = "failed" if failed_brands > 0 and created == 0 and updated == 0 else "success"
        _finish_sync_run(
            db,
            run,
            status=status,
            models_count=len(targets),
            brands_count=len(brand_to_models),
            created=created,
            updated=updated,
            skipped=skipped,
            skipped_by_hp=skipped_by_hp,
            failed_brands=failed_brands,
            pages_fetched=pages_fetched,
        )
        print(
            "summary: "
            f"created={created} updated={updated} skipped={skipped} "
            f"skipped_by_hp={skipped_by_hp} failed_brands={failed_brands} "
            f"pages_fetched={pages_fetched} max_hp={max_hp} dry_run={dry_run}"
        )
        return {
            "status": status,
            "models": len(targets),
            "brands": len(brand_to_models),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "skipped_by_hp": skipped_by_hp,
            "failed_brands": failed_brands,
            "pages_fetched": pages_fetched,
        }
    except Exception as exc:
        if dry_run:
            db.rollback()
        _finish_sync_run(
            db,
            run,
            status="failed",
            models_count=len(targets),
            brands_count=len(brand_to_models),
            created=created,
            updated=updated,
            skipped=skipped,
            skipped_by_hp=skipped_by_hp,
            failed_brands=failed_brands,
            pages_fetched=pages_fetched,
            error_message=str(exc),
        )
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import AV.BY adverts into car_listings for our catalog models")
    parser.add_argument("--user-agent", default="Mozilla/5.0", help="Browser User-Agent")
    parser.add_argument("--make", default=None, help="Filter by make (contains match)")
    parser.add_argument("--model", default=None, help="Filter by model (contains match)")
    parser.add_argument("--limit-models", type=int, default=None, help="Limit number of models to fetch")
    parser.add_argument("--per-model-limit", type=int, default=30, help="Limit adverts per model")
    parser.add_argument("--max-pages", type=int, default=30, help="Max paginated pages per brand")
    parser.add_argument("--max-hp", type=int, default=160, help="Import only adverts with power <= this value")
    parser.add_argument(
        "--no-update-existing",
        action="store_true",
        help="Do not update existing imported AV.BY listings",
    )
    parser.add_argument(
        "--archive-overpowered",
        action="store_true",
        help="Archive existing listing if the same AVBY_ID now has power above max-hp",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write to DB")
    parser.add_argument("--trigger", default="manual", help="Sync trigger label: manual, scheduler, admin")
    args = parser.parse_args()

    try:
        result = run_import(
            user_agent=args.user_agent,
            make=args.make,
            model=args.model,
            limit_models=args.limit_models,
            per_model_limit=args.per_model_limit,
            max_pages=args.max_pages,
            max_hp=args.max_hp,
            update_existing=not args.no_update_existing,
            archive_overpowered=args.archive_overpowered,
            dry_run=args.dry_run,
            trigger=args.trigger,
        )
    except Exception:
        raise SystemExit(1) from None

    if result.get("status") == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
