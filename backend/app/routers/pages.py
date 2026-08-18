import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from jose import JWTError
from sqlalchemy import and_, case, desc, func, or_
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.analytics import EVENT_LABELS, build_analytics_summary, record_auth_event
from app.config import settings
from app.body_type_labels import (
    body_type_db_values_for_filter,
    body_type_filter_options,
    normalize_body_type_label,
)
from app.fuel_type_labels import (
    FUEL_GROUP_HYBRID,
    HYBRID_MARKERS,
    classify_fuel_type,
    fuel_type_db_values_for_filter,
    fuel_type_filter_options,
    normalize_fuel_type_label,
    resolved_catalog_fuel_type,
)
from app.drive_type_labels import normalize_drive_display_label
from app.export_country_labels import (
    EXPORT_COUNTRY_FILTER_OPTIONS,
    is_belarus_export_country,
)
from app.customs_vin import CustomsVinError, lookup_customs_vin, normalize_vin, report_rows, vin_is_valid
from app.avby_accounts import list_active_vin_accounts, serialize_account_public
from app.db import get_db
from app.logging_setup import LOG_SERVICES, LOG_SERVICE_LABELS, format_log_time, log_dir, log_timezone, tail_log
from app.metrics import yandex_metrika_context
from app.listing_enrichment import build_listing_customs_map, get_listing_customs_summary
from app.listing_catalog_link import (
    canonical_model_name as _canonical_model_name,
    fetch_listings_for_catalog_items,
    find_best_catalog_item as _match_catalog_item_for_listing,
    normalize_match_text,
    resolve_catalog_items_for_listings,
    score_listing_catalog_match,
)
from app.models import AvbyServiceAccount, AvbySyncRun, AvbySyncRunVinCheck, CarListing, CatalogItem, CatalogItemPhoto, ListingStatus, User, UserRole
from app.security import decode_token, is_token_revoked
from app.seo import (
    INDEXABLE_CITIES,
    SeoMeta,
    build_robots_txt,
    build_seo_context,
    build_sitemap_entries,
    catalog_generations_seo_meta,
    catalog_item_seo_meta,
    catalog_models_seo_meta,
    catalog_modifications_seo_meta,
    guide_do_160_seo_meta,
    guide_vin_seo_meta,
    home_seo_meta,
    inspection_seo_meta,
    listing_seo_meta,
    listings_feed_seo_meta,
    render_sitemap_xml,
    site_base_url,
)
from app.listing_display import (
    format_mileage_km,
    format_price_rub,
    format_listing_spec_value,
    listing_display_description,
    listing_display_title,
    listing_engine_summary,
    listing_seller_label,
    listing_source_href,
    listing_source_label,
)
from app.listing_photos import (
    pick_listing_cover_url,
    resolve_listing_cover_urls,
    resolve_listing_gallery_urls,
    resolve_listing_gallery_urls_map,
)
from app.storage import build_app_download_url, normalize_display_image_url
from app.sync_run_vin_log import PHASE_LABELS, summarize_sync_run_vin_checks
from app.vin_analytics import SORT_COLUMNS, VinListingSort, build_vin_listings_report
from app.catalog_ratings import (
    DEFAULT_PAGE_SIZE,
    RATING_CHOICES,
    format_rating,
    list_catalog_makes,
    list_generation_ratings,
)

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["body_type_label"] = normalize_body_type_label
templates.env.filters["listing_display_title"] = listing_display_title
templates.env.filters["listing_display_description"] = listing_display_description
templates.env.filters["listing_source_href"] = listing_source_href
templates.env.filters["listing_source_label"] = listing_source_label
templates.env.filters["format_mileage_km"] = format_mileage_km
templates.env.filters["format_price_rub"] = format_price_rub
templates.env.filters["format_listing_spec_value"] = format_listing_spec_value
templates.env.filters["listing_seller_label"] = listing_seller_label
templates.env.filters["listing_engine_summary"] = listing_engine_summary
VERIFICATION_DIR = Path(__file__).resolve().parents[1] / "verification"


SPEC_LABELS_RU = {
    "acceleration0100KmH": "Разгон 0-100 км/ч",
    "backSuspension": "Задняя подвеска",
    "backTrackWidth": "Колея задняя",
    "bodyType": "Тип кузова",
    "boostType": "Наддув",
    "carClass": "Класс авто",
    "co2Emissions": "Выбросы CO2",
    "cityDrivingFuelConsumptionPer100Km": "Расход по городу, л/100 км",
    "compressionRatio": "Степень сжатия",
    "countryBrandItem": "Страна марки",
    "curbWeight": "Снаряженная масса",
    "cylinderBore": "Диаметр цилиндра",
    "cylinderLayout": "Расположение цилиндров",
    "emissionStandards": "Экостандарт",
    "engineCapacity": "Объем двигателя",
    "enginePlacement": "Расположение двигателя",
    "enginePower": "Мощность двигателя",
    "frontBrakes": "Передние тормоза",
    "frontSuspension": "Передняя подвеска",
    "frontTrack": "Колея передняя",
    "frontTrackWidth": "Колея передняя",
    "fuel": "Топливо",
    "fuelTankCapacity": "Объем бака",
    "fullWeight": "Полная масса",
    "gearBoxType": "Коробка передач",
    "groundClearance": "Клиренс",
    "height": "Высота",
    "highwayDrivingFuelConsumptionPer100Km": "Расход по трассе, л/100 км",
    "injectionType": "Тип впрыска",
    "length": "Длина",
    "maxPowerAtRpm": "Обороты макс. мощности",
    "maxPowerHP": "Мощность, л.с.",
    "maxPowerKW": "Мощность, кВт",
    "maxSpeed": "Максимальная скорость",
    "maxTrunkCapacity": "Макс. объем багажника",
    "maximumTorque": "Крутящий момент",
    "minTrunkCapacity": "Мин. объем багажника",
    "mixedDrivingFuelConsumptionPer100Km": "Расход (смешанный), л/100 км",
    "numberOfCylinders": "Количество цилиндров",
    "numberOfDoors": "Количество дверей",
    "numberOfGear": "Количество передач",
    "numberOfSeats": "Количество мест",
    "rearBrakes": "Задние тормоза",
    "rearTrack": "Колея задняя",
    "turningCircle": "Диаметр разворота",
    "cruisingRange": "Запас хода",
    "payload": "Грузоподъемность",
    "presenceOfIntercooler": "Наличие интеркулера",
    "trailerLoadWithBrakes": "Масса прицепа с тормозами",
    "frontRearAxleLoad": "Нагрузка на оси (перед/зад)",
    "loadingHeight": "Погрузочная высота",
    "batteryCapacity": "Емкость батареи",
    "safetyAssessment": "Оценка безопасности",
    "ratingName": "Рейтинг безопасности",
    "engineEndurance": "Ресурс двигателя",
    "batteryChargingTime": "Время зарядки батареи",
    "electricMotorPower": "Мощность электромотора",
    "totalPowerOutput": "Суммарная мощность",
    "cargoCompartmentLengthXWidthXHeight": "Размер грузового отсека (ДxШxВ)",
    "engineCode": "Код двигателя",
    "steeringWheel": "Руль",
    "turnoverOfMaximumTorque": "Обороты макс. крутящего момента",
    "valvesPerCylinder": "Клапанов на цилиндр",
    "wheelSize": "Размер колес",
    "wheelbase": "Колесная база",
    "width": "Ширина",
    "driveType": "Привод",
}

SPEC_SECTIONS = [
    ("Общая информация", ["модель", "поколение", "годы выпуска", "тип кузова", "класс авто", "страна", "руль"]),
    (
        "Двигатель и трансмиссия",
        [
            "двигател",
            "мощност",
            "крутящ",
            "цилинд",
            "клапанов",
            "наддув",
            "коробка",
            "передач",
            "привод",
            "топливо",
            "объем бака",
            "степень сжатия",
            "экостандарт",
            "выбросы",
        ],
    ),
    ("Динамика и расход", ["разгон", "максимальная скорость", "расход", "co2"]),
    (
        "Размеры и масса",
        [
            "длина",
            "ширина",
            "высота",
            "колесная база",
            "колея",
            "клиренс",
            "масса",
            "двер",
            "мест",
            "багаж",
        ],
    ),
    ("Шасси и тормоза", ["подвес", "тормоз", "размер колес", "размер кол"]),
]

SPEC_VALUE_LABELS_RU = {
    "left": "Левый",
    "right": "Правый",
    "fwd": "Передний",
    "rwd": "Задний",
    "awd": "Полный",
    "4wd": "Полный",
    "petrol": "Бензин",
    "gasoline": "Бензин",
    "diesel": "Дизель",
    "hybrid": "Гибрид",
    "electric": "Электро",
    "manual": "Механика",
    "automatic": "Автомат",
    "cvt": "Вариатор",
    "dct": "Робот",
    "robot": "Робот",
    "sedan": "Седан",
    "hatchback": "Хэтчбек",
    "wagon": "Универсал",
    "estate": "Универсал",
    "suv": "Внедорожник",
    "crossover": "Кроссовер",
    "coupe": "Купе",
    "cabrio": "Кабриолет",
    "convertible": "Кабриолет",
    "minivan": "Минивэн",
    "van": "Фургон",
    "pickup": "Пикап",
}

# Brand logos are self-hosted under /static/logos/ (Simple Icons, CC0).
MAKE_LOGO_SLUGS = frozenset(
    {
        "audi",
        "bmw",
        "citroen",
        "dacia",
        "fiat",
        "ford",
        "honda",
        "hyundai",
        "kia",
        "mercedes-benz",
        "mini",
        "nissan",
        "opel",
        "peugeot",
        "renault",
        "skoda",
        "subaru",
        "toyota",
        "volkswagen",
        "volvo",
    }
)


def _resolve_user_from_request(request: Request, db: Session) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != "access" or is_token_revoked(payload):
        return None
    email = payload.get("sub")
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()


def _template_context(request: Request, current_user: User | None, seo: SeoMeta | None = None) -> dict:
    context = {
        "request": request,
        "current_user": current_user,
        "is_authenticated": current_user is not None,
        "is_admin": current_user is not None and current_user.role == UserRole.admin,
    }
    context.update(build_seo_context(request, seo))
    context.update(yandex_metrika_context(request))
    return context


def _listing_match_score(listing: CarListing, item: CatalogItem) -> int:
    return score_listing_catalog_match(listing, item, require_cover=True)


def _extract_photo_url_from_entry(photo: dict) -> str | None:
    if not isinstance(photo, dict):
        return None
    for key in ("big", "medium", "small", "extrasmall"):
        variant = photo.get(key)
        if isinstance(variant, dict) and variant.get("url"):
            return variant["url"]
    if photo.get("url"):
        return photo["url"]
    file_obj = photo.get("file")
    if isinstance(file_obj, dict) and file_obj.get("url"):
        return file_obj["url"]
    return None


def _extract_photo_urls_from_raw_specs(raw_specs: dict) -> list[str]:
    if not isinstance(raw_specs, dict):
        return []
    detail = raw_specs.get("modification_detail") or {}
    if not isinstance(detail, dict):
        return []
    photos = detail.get("photos")
    if not isinstance(photos, list):
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for photo in photos:
        url = _extract_photo_url_from_entry(photo)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _extract_raw_photo_url(raw_specs: dict) -> str | None:
    urls = _extract_photo_urls_from_raw_specs(raw_specs)
    return urls[0] if urls else None


def _fetch_listings_for_catalog_items(items: list[CatalogItem], db: Session) -> dict[tuple[str, str], list[CarListing]]:
    if not items:
        return {}
    pairs = {(item.make or "", _canonical_model_name(item.model)) for item in items if item.make and item.model}
    cache: dict[tuple[str, str], list[CarListing]] = {}
    for make, model in pairs:
        if not make or not model:
            continue
        cache[(make, model)] = (
            db.query(CarListing)
            .filter(
                CarListing.status == ListingStatus.published,
                CarListing.cover_photo_url.isnot(None),
                CarListing.brand.ilike(make),
                CarListing.model.ilike(model),
            )
            .order_by(CarListing.created_at.desc())
            .limit(200)
            .all()
        )
    return cache


def _pick_listing_cover_for_item(item: CatalogItem, listings: list[CarListing]) -> str | None:
    scored: list[tuple[int, int, str]] = []
    for listing in listings:
        score = _listing_match_score(listing, item)
        cover = pick_listing_cover_url(listing)
        if score >= 0 and cover:
            scored.append((score, listing.id, cover))
    if not scored:
        return None
    scored.sort(key=lambda row: (-row[0], -row[1]))
    top_score = scored[0][0]
    top_matches = [row for row in scored if row[0] == top_score]
    return top_matches[item.id % len(top_matches)][2]


def _resolve_catalog_item_cover(
    item: CatalogItem,
    listings_cache: dict[tuple[str, str], list[CarListing]],
) -> str | None:
    listings = listings_cache.get((item.make or "", _canonical_model_name(item.model)), [])
    listing_cover = _pick_listing_cover_for_item(item, listings)
    if listing_cover:
        return listing_cover
    return _extract_raw_photo_url(item.raw_specs or {})


def _find_sibling_stored_cover(item: CatalogItem, db: Session) -> str | None:
    scopes: list[tuple[str, str, str | None]] = []
    if item.generation:
        scopes.append((item.make or "", item.model or "", item.generation))
    scopes.append((item.make or "", item.model or "", None))

    seen: set[tuple[str, str, str | None]] = set()
    for make, model, generation in scopes:
        if not make or not model:
            continue
        scope_key = (make, model, generation)
        if scope_key in seen:
            continue
        seen.add(scope_key)

        query = (
            db.query(CatalogItemPhoto)
            .join(CatalogItem, CatalogItem.id == CatalogItemPhoto.catalog_item_id)
            .filter(
                CatalogItem.make == make,
                CatalogItem.model == model,
                CatalogItem.source_site == "av.by",
            )
        )
        if generation:
            query = query.filter(CatalogItem.generation == generation)
        photo = (
            query.order_by(
                CatalogItemPhoto.is_cover.desc(),
                CatalogItemPhoto.sort_order.asc(),
                CatalogItemPhoto.id.asc(),
            )
            .first()
        )
        if photo:
            return build_app_download_url(photo.storage_key)
    return None


def _build_cover_url_map(item_ids: list[int], db: Session) -> dict[int, str]:
    if not item_ids:
        return {}
    photos = (
        db.query(CatalogItemPhoto)
        .filter(CatalogItemPhoto.catalog_item_id.in_(item_ids))
        .order_by(CatalogItemPhoto.is_cover.desc(), CatalogItemPhoto.sort_order.asc(), CatalogItemPhoto.id.asc())
        .all()
    )
    cover_map: dict[int, str] = {}
    for photo in photos:
        if photo.catalog_item_id in cover_map:
            continue
        cover_map[photo.catalog_item_id] = build_app_download_url(photo.storage_key)

    missing_ids = [item_id for item_id in item_ids if item_id not in cover_map]
    if not missing_ids:
        return cover_map

    items = db.query(CatalogItem).filter(CatalogItem.id.in_(missing_ids)).all()
    listings_cache = _fetch_listings_for_catalog_items(items, db)
    for item in items:
        sibling_cover = _find_sibling_stored_cover(item, db)
        if sibling_cover:
            cover_map[item.id] = sibling_cover
            continue
        cover_url = normalize_display_image_url(_resolve_catalog_item_cover(item, listings_cache))
        if cover_url:
            cover_map[item.id] = cover_url
    return cover_map


def _build_listing_catalog_cover_urls(
    listings: list[CarListing],
    catalog_items: list[CatalogItem],
    db: Session,
) -> dict[int, str]:
    if not listings or not catalog_items:
        return {}

    listing_to_catalog: dict[int, int] = {}
    for listing in listings:
        matched = _match_catalog_item_for_listing(listing, catalog_items)
        if matched:
            listing_to_catalog[listing.id] = matched.id

    cover_by_catalog = _build_cover_url_map(list(listing_to_catalog.values()), db)
    result: dict[int, str] = {}
    for listing in listings:
        cover = pick_listing_cover_url(listing)
        if cover:
            result[listing.id] = cover
            continue
        catalog_id = listing_to_catalog.get(listing.id)
        if catalog_id and catalog_id in cover_by_catalog:
            result[listing.id] = cover_by_catalog[catalog_id]
    return result


def _distinct_values(db: Session, column):
    return [row[0] for row in db.query(column).filter(column.isnot(None)).distinct().order_by(column.asc()).all() if row[0]]


def _year_options(db: Session) -> list[int]:
    from_values = [row[0] for row in db.query(CatalogItem.year_from).filter(CatalogItem.year_from.isnot(None)).distinct().all()]
    to_values = [row[0] for row in db.query(CatalogItem.year_to).filter(CatalogItem.year_to.isnot(None)).distinct().all()]
    years = sorted({*from_values, *to_values}, reverse=True)
    return years


def _catalog_fuel_type_values(db: Session) -> list[str]:
    return _distinct_values(db, CatalogItem.fuel_type)


def _sql_has_hybrid_marker(expr):
    lowered = func.lower(func.coalesce(expr, ""))
    return or_(*(lowered.like(f"%{marker}%") for marker in HYBRID_MARKERS))


def _catalog_engine_type_label_expr():
    return func.coalesce(
        CatalogItem.raw_specs["modification"]["engineType"]["label"].as_string(),
        CatalogItem.raw_specs["modification_detail"]["engineType"]["label"].as_string(),
        CatalogItem.raw_specs["modification_detail"]["engineType"].as_string(),
    )


def _catalog_is_hybrid_predicate():
    return or_(
        _sql_has_hybrid_marker(CatalogItem.fuel_type),
        _sql_has_hybrid_marker(_catalog_engine_type_label_expr()),
    )


def _catalog_fuel_filter_options(db: Session) -> list[str]:
    raw_values = list(_catalog_fuel_type_values(db))
    if db.query(CatalogItem.id).filter(_catalog_is_hybrid_predicate()).limit(1).first():
        raw_values.append("гибрид")
    return fuel_type_filter_options(raw_values)


def _parse_optional_year(value: str | None) -> int | None:
    if value is None:
        return None
    raw = value.strip()
    if raw == "":
        return None
    try:
        year = int(raw)
    except ValueError:
        return None
    if year < 1950 or year > 2100:
        return None
    return year


def _parse_optional_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    raw = value.strip()
    if raw == "":
        return None
    try:
        parsed = int(raw)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _listing_ids_for_catalog_item(db: Session, item: CatalogItem, *, published_only: bool = True) -> list[int]:
    listings = fetch_listings_for_catalog_items(db, [item], limit_per_item=10000).get(item.id, [])
    if published_only:
        listings = [row for row in listings if row.status == ListingStatus.published]
    return [row.id for row in listings]


def _make_model_map(db: Session) -> dict[str, list[str]]:
    rows = (
        db.query(CatalogItem.make, CatalogItem.model)
        .filter(CatalogItem.make.isnot(None), CatalogItem.model.isnot(None), CatalogItem.source_site == "av.by")
        .distinct()
        .order_by(CatalogItem.make.asc(), CatalogItem.model.asc())
        .all()
    )
    mapping: dict[str, list[str]] = {}
    for make, model in rows:
        if not make or not model:
            continue
        mapping.setdefault(make, []).append(_canonical_model_name(model))
    for make, models in mapping.items():
        mapping[make] = sorted(list(set(models)))
    return mapping


def _make_model_generation_map(db: Session) -> dict[str, dict[str, list[str]]]:
    rows = (
        db.query(CatalogItem.make, CatalogItem.model, CatalogItem.generation)
        .filter(
            CatalogItem.make.isnot(None),
            CatalogItem.model.isnot(None),
            CatalogItem.generation.isnot(None),
            CatalogItem.source_site == "av.by",
        )
        .distinct()
        .order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.generation.asc())
        .all()
    )
    mapping: dict[str, dict[str, set[str]]] = {}
    for make, model, generation in rows:
        if not make or not model or not generation:
            continue
        canonical_model = _canonical_model_name(model)
        mapping.setdefault(make, {}).setdefault(canonical_model, set()).add(generation)
    return {
        make: {model: sorted(generations) for model, generations in models.items()}
        for make, models in mapping.items()
    }


def _published_listing_make_models(db: Session) -> set[tuple[str, str]]:
    rows = (
        db.query(CarListing.brand, CarListing.model)
        .filter(
            CarListing.status == ListingStatus.published,
            CarListing.brand.isnot(None),
            CarListing.model.isnot(None),
        )
        .distinct()
        .all()
    )
    return {
        (normalize_match_text(brand), _canonical_model_name(model))
        for brand, model in rows
        if brand and model
    }


def _query_flag(value: str | None) -> bool:
    return value in ("1", "true", "on")


def _passable_year_bounds() -> tuple[int, int]:
    """Manufacture years for passable cars: age >= 3 and <= 5 years."""
    current = datetime.utcnow().year
    return current - 5, current - 3


def _is_passable_year(year: int | None) -> bool:
    if year is None:
        return False
    year_min, year_max = _passable_year_bounds()
    return year_min <= year <= year_max


def _apply_passable_catalog_filter(query):
    year_min, year_max = _passable_year_bounds()
    return query.filter(
        CatalogItem.year_from.isnot(None),
        CatalogItem.year_from <= year_max,
        or_(
            and_(CatalogItem.year_to.isnot(None), CatalogItem.year_to >= year_min),
            and_(CatalogItem.year_to.is_(None), CatalogItem.year_from >= year_min),
        ),
    )


def _listing_brand_model_map(db: Session, *, published_only: bool = True) -> dict[str, list[str]]:
    query = db.query(CarListing.brand, CarListing.model).filter(
        CarListing.brand.isnot(None),
        CarListing.model.isnot(None),
    )
    if published_only:
        query = query.filter(CarListing.status == ListingStatus.published)
    rows = query.distinct().order_by(CarListing.brand.asc(), CarListing.model.asc()).all()
    mapping: dict[str, list[str]] = {}
    for brand, model in rows:
        if not brand or not model:
            continue
        mapping.setdefault(brand, []).append(_canonical_model_name(model))
    for brand, models in mapping.items():
        mapping[brand] = sorted(set(models))
    return mapping


def _listing_year_options(db: Session, *, published_only: bool = True) -> list[int]:
    query = db.query(CarListing.year).filter(CarListing.year.isnot(None))
    if published_only:
        query = query.filter(CarListing.status == ListingStatus.published)
    years = sorted({row[0] for row in query.distinct().all() if row[0]})
    return years


def _distinct_listing_values(db: Session, column, *, published_only: bool = True) -> list[str]:
    query = db.query(column).filter(column.isnot(None))
    if published_only:
        query = query.filter(CarListing.status == ListingStatus.published)
    return [row[0] for row in query.distinct().order_by(column.asc()).all() if row[0]]


def _listing_body_type_values(db: Session, *, published_only: bool = True) -> list[str]:
    return _distinct_listing_values(db, CarListing.body_type, published_only=published_only)


def _catalog_body_type_values(db: Session) -> list[str]:
    return _distinct_values(db, CatalogItem.body_type)


def _listings_filters_payload(request: Request, db: Session, *, published_only: bool = True) -> dict:
    query = request.query_params
    parsed_year_from = _parse_optional_year(query.get("year_from"))
    parsed_year_to = _parse_optional_year(query.get("year_to"))
    catalog_item_id = _parse_optional_int(query.get("catalog_item_id"))
    brand = (query.get("brand") or "").strip()
    model = _canonical_model_name(query.get("model") or "")
    generation = (query.get("generation") or "").strip()
    if catalog_item_id:
        catalog_item = db.get(CatalogItem, catalog_item_id)
        if catalog_item:
            brand = catalog_item.make or brand
            model = _canonical_model_name(catalog_item.model) or model
            generation = catalog_item.generation or generation
    vehicle_rows = _parse_vehicle_filter_rows(query, make_key="brand", model_key="model", generation_key="generation")
    brand_model_map = _merged_listing_brand_model_map(db, published_only=published_only)
    brand_model_generation_map = _make_model_generation_map(db)
    model_options = brand_model_map.get(brand, []) if brand else []
    generation_options = brand_model_generation_map.get(brand, {}).get(model, []) if brand and model else []
    body_type_raw = _listing_body_type_values(db, published_only=published_only)
    body_type_filter = normalize_body_type_label((query.get("body_type") or "").strip()) or ""
    engine_type_raw = _distinct_listing_values(db, CarListing.engine_type, published_only=published_only)
    engine_type_filter = normalize_fuel_type_label((query.get("engine_type") or "").strip()) or ""
    return {
        "filters": {
            "brand": brand,
            "model": model,
            "generation": generation,
            "catalog_item_id": catalog_item_id if catalog_item_id is not None else "",
            "city": (query.get("city") or "").strip(),
            "body_type": body_type_filter,
            "engine_type": engine_type_filter,
            "transmission_type": (query.get("transmission_type") or "").strip(),
            "year_from": parsed_year_from if parsed_year_from is not None else "",
            "year_to": parsed_year_to if parsed_year_to is not None else "",
            "passable": query.get("passable") in ("1", "true", "on"),
            "freshness": query.get("freshness") or "all",
            "sort": query.get("sort") or "newest",
        },
        "options": {
            "brands": sorted(brand_model_map.keys()),
            "models": model_options,
            "generations": generation_options,
            "brand_model_map": brand_model_map,
            "brand_model_generation_map": brand_model_generation_map,
            "cities": _distinct_listing_values(db, CarListing.city, published_only=published_only),
            "body_type": body_type_filter_options(body_type_raw),
            "engine_type": fuel_type_filter_options(engine_type_raw),
            "transmission_type": _distinct_listing_values(db, CarListing.transmission_type, published_only=published_only),
            "years": _listing_year_options(db, published_only=published_only),
        },
        "vehicle_hierarchy": _build_vehicle_hierarchy_payload(
            make_field="brand",
            model_field="model",
            generation_field="generation",
            rows=vehicle_rows,
            make_model_map=brand_model_map,
            make_model_generation_map=brand_model_generation_map,
        ),
    }


def _build_listings_url(
    *,
    brand: str | None = None,
    model: str | None = None,
    generation: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    catalog_item_id: int | None = None,
) -> str:
    if catalog_item_id is not None:
        return "/listings?" + urlencode({"catalog_item_id": catalog_item_id})
    params: dict[str, str | int] = {}
    if brand:
        params["brand"] = brand
    if model:
        params["model"] = model
    if generation:
        params["generation"] = generation
    if year_from is not None:
        params["year_from"] = year_from
    if year_to is not None:
        params["year_to"] = year_to
    if not params:
        return "/listings"
    return "/listings?" + urlencode(params)


def _generation_listings_url(db: Session, item: CatalogItem) -> str | None:
    make = (item.make or "").strip()
    model = _canonical_model_name(item.model)
    generation = (item.generation or "").strip()
    if not make or not model or not generation:
        return None

    generation_items = (
        db.query(CatalogItem)
        .filter(
            CatalogItem.source_site == "av.by",
            CatalogItem.make == make,
            CatalogItem.model == model,
            CatalogItem.generation == generation,
        )
        .all()
    )
    year_from_values = [row.year_from for row in generation_items if row.year_from is not None]
    year_to_values = [row.year_to for row in generation_items if row.year_to is not None]
    return _build_listings_url(
        brand=make,
        model=model,
        generation=generation,
        year_from=min(year_from_values) if year_from_values else item.year_from,
        year_to=max(year_to_values) if year_to_values else item.year_to,
    )


def _merged_listing_brand_model_map(db: Session, *, published_only: bool = True) -> dict[str, list[str]]:
    listing_map = _listing_brand_model_map(db, published_only=published_only)
    catalog_map = _make_model_map(db)
    merged: dict[str, set[str]] = {}
    for brand in set(listing_map) | set(catalog_map):
        merged[brand] = set(listing_map.get(brand, [])) | set(catalog_map.get(brand, []))
    return {brand: sorted(models) for brand, models in merged.items()}


def _parse_vehicle_filter_rows(
    query_params,
    *,
    make_key: str = "make",
    model_key: str = "model",
    generation_key: str = "generation",
) -> list[dict[str, str]]:
    makes = list(query_params.getlist(make_key))
    models = list(query_params.getlist(model_key))
    generations = list(query_params.getlist(generation_key))
    if not makes and not models and not generations:
        return [{"make": "", "model": "", "generation": ""}]
    count = max(len(makes), len(models), len(generations))
    rows: list[dict[str, str]] = []
    for index in range(count):
        make = (makes[index] if index < len(makes) else "").strip()
        model = _canonical_model_name(models[index] if index < len(models) else "")
        generation = (generations[index] if index < len(generations) else "").strip()
        if make or model or generation:
            rows.append({"make": make, "model": model, "generation": generation})
    if not rows:
        return [{"make": "", "model": "", "generation": ""}]
    return rows


def _vehicle_rows_to_query_pairs(
    rows: list[dict[str, str]],
    *,
    make_key: str,
    model_key: str,
    generation_key: str,
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for row in rows:
        if not (row.get("make") or row.get("model") or row.get("generation")):
            continue
        pairs.append((make_key, row.get("make") or ""))
        pairs.append((model_key, row.get("model") or ""))
        pairs.append((generation_key, row.get("generation") or ""))
    return pairs


def _apply_catalog_vehicle_rows_filter(query, rows: list[dict[str, str]]):
    active_rows = [row for row in rows if row.get("make") or row.get("model") or row.get("generation")]
    if not active_rows:
        return query
    conditions = []
    for row in active_rows:
        parts = []
        if row.get("make"):
            parts.append(CatalogItem.make.ilike(f"%{row['make']}%"))
        if row.get("model"):
            parts.append(CatalogItem.model == row["model"])
        if row.get("generation"):
            parts.append(CatalogItem.generation == row["generation"])
        if parts:
            conditions.append(and_(*parts))
    if not conditions:
        return query
    return query.filter(or_(*conditions))


def _apply_listing_vehicle_rows_filter(query, rows: list[dict[str, str]]):
    active_rows = [row for row in rows if row.get("make") or row.get("model") or row.get("generation")]
    if not active_rows:
        return query
    conditions = []
    for row in active_rows:
        parts = []
        if row.get("make"):
            parts.append(CarListing.brand == row["make"])
        if row.get("model"):
            parts.append(CarListing.model.ilike(row["model"]))
        if row.get("generation"):
            parts.append(CarListing.generation == row["generation"])
        if parts:
            conditions.append(and_(*parts))
    if not conditions:
        return query
    return query.filter(or_(*conditions))


def _build_vehicle_hierarchy_payload(
    *,
    make_field: str,
    model_field: str,
    generation_field: str,
    rows: list[dict[str, str]],
    make_model_map: dict[str, list[str]],
    make_model_generation_map: dict[str, dict[str, list[str]]],
) -> dict:
    return {
        "make_field": make_field,
        "model_field": model_field,
        "generation_field": generation_field,
        "rows": rows,
        "labels": {"make": "Марка", "model": "Модель", "generation": "Поколение"},
        "config": {
            "makes": sorted(make_model_map.keys()),
            "modelMap": make_model_map,
            "generationMap": make_model_generation_map,
        },
    }


def _catalog_sidebar_payload(request: Request, db: Session) -> dict:
    query = request.query_params
    parsed_year_from = _parse_optional_year(query.get("year_from"))
    parsed_year_to = _parse_optional_year(query.get("year_to"))
    raw_page_size = query.get("page_size", "20")
    try:
        page_size = int(raw_page_size)
    except (TypeError, ValueError):
        page_size = 20
    make = (query.get("make") or "").strip()
    model = _canonical_model_name(query.get("model") or "")
    generation = (query.get("generation") or "").strip()
    vehicle_rows = _parse_vehicle_filter_rows(query, make_key="make", model_key="model", generation_key="generation")
    make_model_map = _make_model_map(db)
    make_model_generation_map = _make_model_generation_map(db)
    model_options = make_model_map.get(make, []) if make else []
    generation_options = make_model_generation_map.get(make, {}).get(model, []) if make and model else []
    body_type_raw = _catalog_body_type_values(db)
    body_type_filter = normalize_body_type_label(query.get("body_type") or "") or ""
    fuel_type_filter = normalize_fuel_type_label(query.get("fuel_type") or "") or ""
    return {
        "filters": {
            "make": make,
            "model": model,
            "generation": generation,
            "body_type": body_type_filter,
            "export_country": query.get("export_country", ""),
            "fuel_type": fuel_type_filter,
            "transmission": query.get("transmission", ""),
            "year_from": parsed_year_from if parsed_year_from is not None else "",
            "year_to": parsed_year_to if parsed_year_to is not None else "",
            "sort": query.get("sort", "year_desc"),
            "page_size": page_size,
            "exact_hp": _query_flag(query.get("exact_hp")),
            "with_listings": _query_flag(query.get("with_listings")),
        },
        "options": {
            "makes": sorted(make_model_map.keys()),
            "models": model_options,
            "generations": generation_options,
            "make_model_map": make_model_map,
            "make_model_generation_map": make_model_generation_map,
            "body_type": body_type_filter_options(body_type_raw),
            "export_country": list(EXPORT_COUNTRY_FILTER_OPTIONS),
            "fuel_type": _catalog_fuel_filter_options(db),
            "transmission": _distinct_values(db, CatalogItem.transmission),
            "years": _year_options(db),
        },
        "vehicle_hierarchy": _build_vehicle_hierarchy_payload(
            make_field="make",
            model_field="model",
            generation_field="generation",
            rows=vehicle_rows,
            make_model_map=make_model_map,
            make_model_generation_map=make_model_generation_map,
        ),
    }


_CATALOG_FILTER_PARAM_KEYS = ("body_type", "export_country", "fuel_type", "transmission", "year_from", "year_to")
_CATALOG_NAV_EXCLUDE = frozenset({"make", "model", "generation"})


def _parse_catalog_sidebar_filter_kwargs(request: Request) -> tuple[dict, bool, bool]:
    q = request.query_params
    exact_hp = _query_flag(q.get("exact_hp"))
    with_listings = _query_flag(q.get("with_listings"))
    return (
        {
            "body_type": normalize_body_type_label(q.get("body_type") or "") or None,
            "export_country": (q.get("export_country") or "").strip() or None,
            "fuel_type": normalize_fuel_type_label(q.get("fuel_type") or "") or None,
            "transmission": (q.get("transmission") or "").strip() or None,
            "parsed_year_from": _parse_optional_year(q.get("year_from")),
            "parsed_year_to": _parse_optional_year(q.get("year_to")),
        },
        exact_hp,
        with_listings,
    )


def _catalog_filter_query_pairs(
    request: Request,
    *,
    exclude: frozenset[str] = frozenset(),
    include_makes: list[str] | None = None,
) -> list[tuple[str, str]]:
    q = request.query_params
    pairs: list[tuple[str, str]] = []
    for key in _CATALOG_FILTER_PARAM_KEYS:
        if key in exclude:
            continue
        val = (q.get(key) or "").strip()
        if val:
            pairs.append((key, val))
    if "exact_hp" not in exclude and _query_flag(q.get("exact_hp")):
        pairs.append(("exact_hp", "1"))
    if "with_listings" not in exclude and _query_flag(q.get("with_listings")):
        pairs.append(("with_listings", "1"))
    if "make" not in exclude:
        makes = include_makes if include_makes is not None else [m.strip() for m in q.getlist("make") if m.strip()]
        for make_name in makes:
            pairs.append(("make", make_name))
    if "model" not in exclude:
        model = _canonical_model_name(q.get("model") or "")
        if model:
            pairs.append(("model", model))
    if "generation" not in exclude:
        generation = (q.get("generation") or "").strip()
        if generation:
            pairs.append(("generation", generation))
    return pairs


def _build_catalog_filtered_url(path: str, pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return path
    return path + "?" + urlencode(pairs)


def _catalog_items_base_query(db: Session, request: Request) -> tuple:
    filter_kwargs, exact_hp, with_listings = _parse_catalog_sidebar_filter_kwargs(request)
    query = db.query(CatalogItem).filter(CatalogItem.source_site == "av.by")
    query = _apply_hp_filter(query, exact_hp=exact_hp)
    query = _apply_catalog_item_filters(query, db=db, **filter_kwargs)
    return query, exact_hp, with_listings


def _apply_freshness_filter(query, freshness: str | None):
    if not freshness or freshness == "all":
        return query
    now = datetime.utcnow()
    if freshness == "day":
        since = now - timedelta(days=1)
    elif freshness == "week":
        since = now - timedelta(days=7)
    elif freshness == "month":
        since = now - timedelta(days=30)
    else:
        return query
    return query.filter(CarListing.created_at >= since)


def _resolve_listing_cover_urls(listings: list[CarListing], db: Session) -> dict[int, str]:
    if not listings:
        return {}
    result = resolve_listing_cover_urls(listings)
    need_catalog: set[tuple[str, str]] = set()
    for listing in listings:
        if listing.id in result:
            continue
        make = (listing.brand or "").strip()
        model = _canonical_model_name(listing.model)
        if make and model:
            need_catalog.add((make, model))

    catalog_by_pair: dict[tuple[str, str], list[CatalogItem]] = {}
    for make, model in need_catalog:
        catalog_by_pair[(make, model)] = (
            _apply_max_hp_filter(
                db.query(CatalogItem).filter(
                    CatalogItem.source_site == "av.by",
                    CatalogItem.make.ilike(make),
                    CatalogItem.model == model,
                )
            )
            .order_by(CatalogItem.year_from.desc())
            .limit(40)
            .all()
        )

    for listing in listings:
        if listing.id in result:
            continue
        make = (listing.brand or "").strip()
        model = _canonical_model_name(listing.model)
        catalog_items = catalog_by_pair.get((make, model), [])
        if catalog_items:
            fallback = _build_listing_catalog_cover_urls([listing], catalog_items, db)
            if listing.id in fallback:
                result[listing.id] = fallback[listing.id]
    return result


def _normalize_vin(vin: str | None) -> str:
    return normalize_vin(vin)


def _vin_is_valid(vin: str) -> bool:
    return vin_is_valid(vin)


def _resolve_latest_generation(db: Session, make: str, model: str) -> str | None:
    canonical_model = _canonical_model_name(model)
    rows = (
        db.query(CatalogItem.generation, CatalogItem.year_from)
        .filter(
            CatalogItem.make == make,
            CatalogItem.model == canonical_model,
            CatalogItem.generation.isnot(None),
            CatalogItem.source_site == "av.by",
        )
        .order_by(case((CatalogItem.source_site == "av.by", 0), else_=1), CatalogItem.year_from.desc())
        .all()
    )
    if not rows:
        return None
    best = None
    best_score = None
    for generation, year_from in rows:
        if not generation:
            continue
        score = (year_from or 0, generation)
        if best_score is None or score > best_score:
            best_score = score
            best = generation
    return best


def _humanize_spec_key(key: str) -> str:
    if key in SPEC_LABELS_RU:
        return SPEC_LABELS_RU[key]
    snake = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).replace("-", "_").lower()
    return snake.replace("_", " ").capitalize()


def _humanize_spec_value(value: str) -> str:
    source = str(value).strip()
    if not source:
        return "—"
    normalized = source.lower()
    if normalized in SPEC_VALUE_LABELS_RU:
        return SPEC_VALUE_LABELS_RU[normalized]
    return source


def _make_logo_url(make: str | None) -> str | None:
    if not make:
        return None
    key = make.strip().lower()
    if key not in MAKE_LOGO_SLUGS:
        return None
    return f"/static/logos/{key}.svg"


def _distinct_canonical_models(db: Session) -> list[str]:
    raw_models = _distinct_values(db, CatalogItem.model)
    canonical = {_canonical_model_name(m) for m in raw_models if m}
    return sorted(canonical)


def _build_spec_rows(item: CatalogItem) -> list[tuple[str, str]]:
    raw = item.raw_specs or {}
    details = raw.get("modification_detail") or {}
    ignored = {"photos", "generation", "wheelSizes", "id", "name"}
    rows: list[tuple[str, str]] = []
    if isinstance(details, dict):
        for key, value in details.items():
            if key in ignored or value in (None, "", []):
                continue
            if isinstance(value, dict):
                display = value.get("label") or value.get("name") or value.get("id")
                if not display:
                    continue
            else:
                display = str(value)
            rows.append((_humanize_spec_key(key), _humanize_spec_value(display)))

    # Fallback for rows imported before deep detail was available.
    short_mod = raw.get("modification") or {}
    if not rows and isinstance(short_mod, dict):
        short_map = {
            "engineType": "Топливо",
            "gearBoxType": "Коробка передач",
            "driveType": "Привод",
            "bodyType": "Тип кузова",
        }
        for key, label in short_map.items():
            value = short_mod.get(key)
            if isinstance(value, dict):
                display = value.get("label") or value.get("name") or value.get("id")
            else:
                display = value
            if display:
                rows.append((label, _humanize_spec_value(display)))
    return rows


def _resolve_best_spec_rows(item: CatalogItem, db: Session) -> list[tuple[str, str]]:
    rows = _build_spec_rows(item)
    if rows:
        return rows

    candidates = (
        db.query(CatalogItem)
        .filter(
            CatalogItem.make == item.make,
            CatalogItem.model == item.model,
            CatalogItem.generation == item.generation,
            CatalogItem.raw_specs.isnot(None),
            CatalogItem.source_site == "av.by",
        )
        .order_by(case((CatalogItem.source_site == "av.by", 0), else_=1), CatalogItem.created_at.desc())
        .limit(40)
        .all()
    )
    for candidate in candidates:
        candidate_rows = _build_spec_rows(candidate)
        if candidate_rows:
            return candidate_rows
    return []


def _build_compare_value_map(item: CatalogItem, db: Session) -> dict[str, str]:
    values: dict[str, str] = {}
    for label, value in _resolve_best_spec_rows(item, db):
        values.setdefault(label, value)
    return values


def _parse_numeric_value(value: str) -> float | None:
    if not value:
        return None
    cleaned = value.replace("\u00a0", " ")
    cleaned = re.sub(r"(?<=\d)\s+(?=\d)", "", cleaned)
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", cleaned)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def _section_for_label(label: str) -> str:
    normalized = label.lower()
    for section_name, keywords in SPEC_SECTIONS:
        if any(keyword in normalized for keyword in keywords):
            return section_name
    return "Прочее"


def _group_spec_rows(spec_rows: list[tuple[str, str]]) -> list[dict]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for label, value in spec_rows:
        section = _section_for_label(label)
        grouped.setdefault(section, []).append({"label": label, "value": value})

    ordered_sections: list[dict] = []
    defined_order = [name for name, _ in SPEC_SECTIONS] + ["Прочее"]
    for section_name in defined_order:
        rows = grouped.get(section_name, [])
        if rows:
            ordered_sections.append({"title": section_name, "rows": rows})
    return ordered_sections


def _modification_display_name(item: CatalogItem) -> str:
    raw = item.raw_specs or {}
    detail = raw.get("modification_detail") or {}
    mod = raw.get("modification") or {}
    for source in (detail, mod):
        if isinstance(source, dict):
            name = (source.get("name") or "").strip()
            if name:
                return name
    return (item.source_external_id or "").strip()


def _modification_attrs(item: CatalogItem) -> dict[str, str]:
    raw = item.raw_specs or {}
    detail = raw.get("modification_detail") or {}

    def _extract(key: str) -> str:
        value = detail.get(key) if isinstance(detail, dict) else None
        if value is None:
            return ""
        if isinstance(value, dict):
            value = value.get("label") or value.get("name") or value.get("id")
        return _humanize_spec_value(value)

    volume_raw = ""
    if isinstance(detail, dict):
        volume_raw = str(detail.get("engineCapacity") or "").strip()
    if volume_raw.isdigit():
        volume = f"{int(volume_raw) / 1000:.1f} л".replace(".0", "")
    elif item.engine_volume_l is not None:
        volume = f"{item.engine_volume_l} л"
    else:
        volume = ""

    power_raw = ""
    if isinstance(detail, dict):
        power_raw = str(detail.get("maxPowerHP") or detail.get("enginePower") or "").strip()
    if power_raw.isdigit():
        power = f"{power_raw} л.с."
    elif item.engine_power_hp is not None:
        power = f"{item.engine_power_hp} л.с."
    else:
        power = ""

    effective_fuel = resolved_catalog_fuel_type(item.fuel_type, raw)
    fuel_label = classify_fuel_type(effective_fuel) if effective_fuel else None
    if not fuel_label:
        fuel_label = classify_fuel_type(_extract("fuel") or item.fuel_type)

    drive_raw = _extract("driveType") or _humanize_spec_value(item.drivetrain or "")

    return {
        "volume": volume,
        "power": power,
        "fuel": fuel_label or "—",
        "gearbox": _extract("gearBoxType") or _humanize_spec_value(item.transmission or ""),
        "drive": normalize_drive_display_label(drive_raw) if drive_raw else "—",
    }


def _format_catalog_year_range(item: CatalogItem) -> str:
    if item.year_from is not None and item.year_to is not None:
        if item.year_from == item.year_to:
            return str(item.year_from)
        return f"{item.year_from}–{item.year_to}"
    if item.year_from is not None:
        return f"{item.year_from}–"
    if item.year_to is not None:
        return f"–{item.year_to}"
    return "—"


def _modification_row(item: CatalogItem) -> dict:
    attrs = _modification_attrs(item)
    return {
        "id": item.id,
        "name": _modification_display_name(item) or f"{item.make or ''} {item.model or ''}".strip(),
        "volume": attrs.get("volume") or "—",
        "power": attrs.get("power") or "—",
        "fuel": attrs.get("fuel") or "—",
        "gearbox": attrs.get("gearbox") or "—",
        "drive": attrs.get("drive") or "—",
        "body_type": normalize_body_type_label(item.body_type) or "—",
        "rating": float(item.rating) if item.rating is not None else None,
        "url": f"/catalog/item/{item.id}",
    }


def _catalog_items_year_range(items: list[CatalogItem]) -> str | None:
    if not items:
        return None
    year_from_values = [item.year_from for item in items if item.year_from is not None]
    year_to_values = [item.year_to for item in items if item.year_to is not None]
    if not year_from_values and not year_to_values:
        return None
    year_from = min(year_from_values) if year_from_values else None
    year_to = max(year_to_values) if year_to_values else None
    if year_from is not None and year_to is not None:
        if year_from == year_to:
            return str(year_from)
        return f"{year_from}–{year_to}"
    if year_from is not None:
        return f"{year_from}–"
    if year_to is not None:
        return f"–{year_to}"
    return None


def _modification_power_sort_key(row: dict) -> int:
    power = row.get("power") or ""
    match = re.search(r"(\d+)", power)
    return int(match.group(1)) if match else 0


def _build_modification_table_groups(items: list[CatalogItem]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    order: list[str] = []
    for item in items:
        row = _modification_row(item)
        body_type = row["body_type"] or "—"
        if body_type not in grouped:
            grouped[body_type] = []
            order.append(body_type)
        grouped[body_type].append(row)

    result: list[dict] = []
    for body_type in order:
        rows = grouped[body_type]
        rows.sort(key=_modification_power_sort_key, reverse=True)
        result.append({"body_type": body_type, "rows": rows})
    return result


def _build_modification_titles(items: list[CatalogItem]) -> dict[int, str]:
    base_names: dict[int, str] = {}
    attrs_map: dict[int, dict[str, str]] = {}
    groups: dict[str, list[int]] = {}

    for item in items:
        base = _modification_display_name(item) or f"{item.make or ''} {item.model or ''}".strip()
        base_names[item.id] = base
        attrs_map[item.id] = _modification_attrs(item)
        groups.setdefault(base, []).append(item.id)

    result: dict[int, str] = {}
    for item in items:
        item_id = item.id
        base = base_names[item_id]
        attrs = attrs_map[item_id]
        duplicates = groups.get(base, [])

        # Always show key technical differentiators; for duplicate names it's critical.
        parts: list[str] = []
        for key in ("volume", "power", "fuel", "gearbox", "drive"):
            value = attrs.get(key, "").strip()
            if value and value != "—":
                parts.append(value)

        if duplicates and len(duplicates) > 1 and not parts:
            parts.append(f"ID {item_id}")

        if parts:
            result[item_id] = f"{base} ({' · '.join(parts)})"
        else:
            result[item_id] = base
    return result


def _apply_group_rating(group: dict, item: CatalogItem) -> None:
    if group.get("rating") is not None or item.rating is None:
        return
    group["rating"] = float(item.rating)


def _dedupe_modifications(items: list[CatalogItem]) -> list[CatalogItem]:
    unique: dict[tuple[str, str, str, str], CatalogItem] = {}
    for item in items:
        attrs = _modification_attrs(item)
        key = (
            (item.make or "").strip().lower(),
            (item.model or "").strip().lower(),
            (item.generation or "").strip().lower(),
            _modification_display_name(item).lower(),
            attrs.get("volume", "").lower(),
            attrs.get("power", "").lower(),
            attrs.get("fuel", "").lower(),
            attrs.get("gearbox", "").lower(),
            attrs.get("drive", "").lower(),
        )
        if key not in unique:
            unique[key] = item
            continue
        # Prefer AV.BY rows and newer rows when duplicates collide.
        current = unique[key]
        current_score = (0 if current.source_site == "av.by" else 1, current.created_at)
        new_score = (0 if item.source_site == "av.by" else 1, item.created_at)
        if new_score < current_score:
            unique[key] = item
    return list(unique.values())


def _apply_catalog_item_filters(
    query,
    *,
    db: Session,
    vehicle_rows: list[dict[str, str]] | None = None,
    make: str | None = None,
    model: str | None = None,
    generation: str | None = None,
    body_type: str | None = None,
    export_country: str | None = None,
    fuel_type: str | None = None,
    transmission: str | None = None,
    parsed_year_from: int | None = None,
    parsed_year_to: int | None = None,
):
    if vehicle_rows:
        query = _apply_catalog_vehicle_rows_filter(query, vehicle_rows)
    else:
        if make:
            query = query.filter(CatalogItem.make.ilike(f"%{make}%"))
        if model:
            query = query.filter(CatalogItem.model == _canonical_model_name(model))
        if generation:
            query = query.filter(CatalogItem.generation == generation)
    if body_type:
        canonical = normalize_body_type_label(body_type) or body_type
        match_values = body_type_db_values_for_filter(_catalog_body_type_values(db), canonical)
        if match_values:
            query = query.filter(CatalogItem.body_type.in_(match_values))
    if export_country and not is_belarus_export_country(export_country):
        query = query.filter(CatalogItem.export_country.ilike(f"%{export_country}%"))
    if fuel_type:
        canonical = normalize_fuel_type_label(fuel_type) or fuel_type
        hybrid_pred = _catalog_is_hybrid_predicate()
        if canonical == FUEL_GROUP_HYBRID:
            query = query.filter(hybrid_pred)
        else:
            match_values = fuel_type_db_values_for_filter(_catalog_fuel_type_values(db), canonical)
            if match_values:
                query = query.filter(CatalogItem.fuel_type.in_(match_values))
            else:
                query = query.filter(CatalogItem.fuel_type.ilike(f"%{fuel_type}%"))
            query = query.filter(~hybrid_pred)
    if transmission:
        query = query.filter(CatalogItem.transmission.ilike(f"%{transmission}%"))
    if parsed_year_from is not None:
        query = query.filter(CatalogItem.year_from >= parsed_year_from)
    if parsed_year_to is not None:
        query = query.filter(CatalogItem.year_to <= parsed_year_to)
    return query


def _apply_hp_filter(query, *, max_hp: int = 160, exact_hp: bool = False):
    if exact_hp:
        return query.filter(CatalogItem.engine_power_hp == max_hp)
    return query.filter(or_(CatalogItem.engine_power_hp.is_(None), CatalogItem.engine_power_hp <= max_hp))


def _apply_max_hp_filter(query, max_hp: int = 160):
    return _apply_hp_filter(query, max_hp=max_hp, exact_hp=False)


def _home_stats(db: Session) -> dict:
    hp_filter = or_(CatalogItem.engine_power_hp.is_(None), CatalogItem.engine_power_hp <= 160)
    catalog_filters = (
        CatalogItem.source_site == "av.by",
        hp_filter,
    )
    catalog_items_count = (
        db.query(CatalogItem)
        .filter(*catalog_filters)
        .count()
    )
    catalog_makes_count = int(
        db.query(func.count(func.distinct(CatalogItem.make)))
        .filter(CatalogItem.make.isnot(None), *catalog_filters)
        .scalar()
        or 0
    )
    listings_query = db.query(CarListing).filter(CarListing.status == ListingStatus.published)
    listings_count = listings_query.count()
    year_min, year_max = _passable_year_bounds()
    passable_listings_count = listings_query.filter(
        CarListing.year.isnot(None),
        CarListing.year >= year_min,
        CarListing.year <= year_max,
    ).count()
    return {
        "catalog_items_count": catalog_items_count,
        "catalog_makes_count": catalog_makes_count,
        "listings_count": listings_count,
        "passable_listings_count": passable_listings_count,
        "passable_year_from": year_min,
        "passable_year_to": year_max,
    }


def _home_popular_makes(db: Session, *, limit: int = 8) -> list[dict]:
    rows = (
        _apply_max_hp_filter(db.query(CatalogItem))
        .filter(CatalogItem.make.isnot(None), CatalogItem.source_site == "av.by")
        .order_by(CatalogItem.make.asc(), CatalogItem.created_at.desc())
        .all()
    )
    grouped: dict[str, dict] = {}
    for item in rows:
        make = (item.make or "").strip()
        if not make:
            continue
        if make not in grouped:
            grouped[make] = {"make": make, "count": 0, "first_id": item.id}
        grouped[make]["count"] += 1
    makes = sorted(grouped.values(), key=lambda row: (-row["count"], row["make"]))[:limit]
    for make in makes:
        make["models_url"] = "/catalog/models?" + urlencode({"make": make["make"]})
        make["logo_url"] = _make_logo_url(make["make"])
    return makes


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    latest_listings = (
        db.query(CarListing)
        .filter(CarListing.status == ListingStatus.published)
        .order_by(desc(CarListing.created_at))
        .limit(6)
        .all()
    )
    context = _template_context(request, current_user, home_seo_meta(request))
    context.update(_home_stats(db))
    context["popular_makes"] = _home_popular_makes(db)
    context["latest_listings"] = latest_listings
    context["listing_cover_urls"] = _resolve_listing_cover_urls(latest_listings, db)
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/design-preview")
def design_preview(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    latest_listings = (
        db.query(CarListing)
        .filter(CarListing.status == ListingStatus.published)
        .order_by(desc(CarListing.created_at))
        .limit(6)
        .all()
    )
    context = _template_context(request, current_user)
    context.update(_home_stats(db))
    context["popular_makes"] = _home_popular_makes(db)
    context["latest_listings"] = latest_listings
    context["listing_cover_urls"] = _resolve_listing_cover_urls(latest_listings, db)
    return templates.TemplateResponse(request, "design_preview.html", context)


@router.get("/robots.txt", include_in_schema=False)
def robots_txt(request: Request):
    base = site_base_url(request)
    return PlainTextResponse(build_robots_txt(base), media_type="text/plain; charset=utf-8")


@router.get("/yandex_{code}.html", include_in_schema=False)
def yandex_webmaster_verification(code: str):
    path = VERIFICATION_DIR / f"yandex_{code}.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return HTMLResponse(path.read_text(encoding="utf-8"), media_type="text/html; charset=utf-8")


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(request: Request, db: Session = Depends(get_db)):
    base = site_base_url(request)
    entries = build_sitemap_entries(db, base)
    xml = render_sitemap_xml(entries)
    return Response(content=xml, media_type="application/xml; charset=utf-8")


@router.get("/listings")
def listings_page(
    request: Request,
    city: str | None = Query(default=None),
    body_type: str | None = Query(default=None),
    engine_type: str | None = Query(default=None),
    transmission_type: str | None = Query(default=None),
    year_from: str | None = Query(default=None),
    year_to: str | None = Query(default=None),
    catalog_item_id: int | None = Query(default=None),
    passable: bool = Query(default=False),
    freshness: str = Query(default="all"),
    sort: str = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    vehicle_rows = _parse_vehicle_filter_rows(request.query_params, make_key="brand", model_key="model", generation_key="generation")
    parsed_year_from = _parse_optional_year(year_from)
    parsed_year_to = _parse_optional_year(year_to)
    query = db.query(CarListing)
    is_admin = current_user is not None and current_user.role == UserRole.admin
    if not is_admin:
        query = query.filter(CarListing.status == ListingStatus.published)

    catalog_item_filter = db.get(CatalogItem, catalog_item_id) if catalog_item_id else None
    if catalog_item_filter:
        listing_ids = _listing_ids_for_catalog_item(db, catalog_item_filter, published_only=not is_admin)
        query = query.filter(CarListing.id.in_(listing_ids or [-1]))
    else:
        query = _apply_listing_vehicle_rows_filter(query, vehicle_rows)
    if city:
        query = query.filter(CarListing.city == city)
    if body_type:
        canonical = normalize_body_type_label(body_type) or body_type
        match_values = body_type_db_values_for_filter(
            _listing_body_type_values(db, published_only=not is_admin),
            canonical,
        )
        if match_values:
            query = query.filter(CarListing.body_type.in_(match_values))
    if engine_type:
        canonical = normalize_fuel_type_label(engine_type) or engine_type
        match_values = fuel_type_db_values_for_filter(
            _distinct_listing_values(db, CarListing.engine_type, published_only=not is_admin),
            canonical,
        )
        if match_values:
            query = query.filter(CarListing.engine_type.in_(match_values))
        else:
            query = query.filter(CarListing.engine_type.ilike(f"%{engine_type}%"))
    if transmission_type:
        query = query.filter(CarListing.transmission_type == transmission_type)
    if parsed_year_from is not None:
        query = query.filter(CarListing.year >= parsed_year_from)
    if parsed_year_to is not None:
        query = query.filter(CarListing.year <= parsed_year_to)
    if passable:
        year_min, year_max = _passable_year_bounds()
        query = query.filter(CarListing.year >= year_min, CarListing.year <= year_max)
    query = _apply_freshness_filter(query, freshness)

    if sort == "price_asc":
        query = query.order_by(CarListing.price.asc(), CarListing.created_at.desc())
    elif sort == "price_desc":
        query = query.order_by(CarListing.price.desc(), CarListing.created_at.desc())
    elif sort == "year_desc":
        query = query.order_by(CarListing.year.desc(), CarListing.created_at.desc())
    elif sort == "year_asc":
        query = query.order_by(CarListing.year.asc(), CarListing.created_at.desc())
    else:
        query = query.order_by(CarListing.created_at.desc())

    total = query.count()
    offset = (page - 1) * page_size
    listings = query.offset(offset).limit(page_size).all()
    context = _template_context(request, current_user)
    context["listings"] = listings
    context["listing_cover_urls"] = _resolve_listing_cover_urls(listings, db)
    context["listing_gallery_urls"] = resolve_listing_gallery_urls_map(listings, limit=5)
    context["listing_catalog_items"] = resolve_catalog_items_for_listings(db, listings)
    context["total"] = total
    context["page"] = page
    context["page_size"] = page_size
    context["total_pages"] = max(1, (total + page_size - 1) // page_size)
    context["has_prev"] = page > 1
    context["has_next"] = offset + len(listings) < total
    context["listings_filters"] = _listings_filters_payload(request, db, published_only=not is_admin)
    context["catalog_item_filter"] = catalog_item_filter
    normalized_body_type = context["listings_filters"]["filters"]["body_type"] or None

    query_params = {
        "catalog_item_id": catalog_item_id if catalog_item_id else None,
        "city": city or None,
        "body_type": normalized_body_type,
        "engine_type": engine_type or None,
        "transmission_type": transmission_type or None,
        "year_from": parsed_year_from,
        "year_to": parsed_year_to,
        "passable": "1" if passable else None,
        "freshness": freshness if freshness and freshness != "all" else None,
        "sort": sort if sort else None,
        "page_size": page_size if page_size != 20 else None,
    }

    def build_page_url(page_num: int) -> str:
        pairs = _vehicle_rows_to_query_pairs(vehicle_rows, make_key="brand", model_key="model", generation_key="generation")
        for key, value in query_params.items():
            if value not in (None, ""):
                pairs.append((key, str(value)))
        pairs.append(("page", str(page_num)))
        return "/listings?" + urlencode(pairs)

    context["prev_url"] = build_page_url(page - 1) if context["has_prev"] else None
    context["next_url"] = build_page_url(page + 1) if context["has_next"] else None
    context["listing_customs_map"] = build_listing_customs_map(db, listings) if listings else {}

    brand = None
    model = None
    if len(vehicle_rows) == 1:
        brand = (vehicle_rows[0].get("make") or "").strip() or None
        model = (vehicle_rows[0].get("model") or "").strip() or None
    elif len(vehicle_rows) > 1:
        brand = "__multi__"
    noisy_filters = bool(
        catalog_item_id
        or body_type
        or engine_type
        or transmission_type
        or parsed_year_from is not None
        or parsed_year_to is not None
        or passable
        or (freshness and freshness != "all")
        or (sort and sort != "newest")
        or page_size != 20
        or brand == "__multi__"
        or any((row.get("generation") or "").strip() for row in vehicle_rows)
        or (city and city not in INDEXABLE_CITIES and not brand)
    )
    seo_brand = None if brand == "__multi__" else brand
    context.update(
        build_seo_context(
            request,
            listings_feed_seo_meta(
                city=city,
                brand=seo_brand,
                model=model if seo_brand else None,
                page=page,
                total=total,
                noisy_filters=noisy_filters or (brand == "__multi__"),
            ),
        )
    )
    return templates.TemplateResponse(request, "listings.html", context)


@router.get("/listings/{listing_id}")
def listing_item(request: Request, listing_id: int, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if listing and listing.status != ListingStatus.published:
        if current_user is None or current_user.role != UserRole.admin:
            listing = None
    seo = None
    if listing:
        cover_urls = _resolve_listing_cover_urls([listing], db)
        seo = listing_seo_meta(
            listing,
            cover_url=cover_urls.get(listing.id),
            base=site_base_url(request),
        )
    else:
        seo = SeoMeta(
            title="Объявление не найдено — Auto160",
            description="Объявление не найдено или снято с публикации.",
            path=f"/listings/{listing_id}",
            noindex=True,
        )
    context = _template_context(request, current_user, seo)
    context["listing"] = listing
    if listing:
        catalog_items = resolve_catalog_items_for_listings(db, [listing])
        context["catalog_item"] = catalog_items.get(listing.id)
        context["gallery_urls"] = resolve_listing_gallery_urls(listing)
        city = (listing.city or "").strip()
        context["city_listings_url"] = (
            f"/listings?city={quote(city)}" if city in INDEXABLE_CITIES else None
        )
        context["vin_guide_url"] = "/guides/vin"
    else:
        context["catalog_item"] = None
        context["gallery_urls"] = []
        context["city_listings_url"] = None
        context["vin_guide_url"] = "/guides/vin"
    context["listing_customs"] = get_listing_customs_summary(db, listing) if listing else None
    status_code = 200 if listing else 404
    return templates.TemplateResponse(
        request, "listing_detail.html", context, status_code=status_code
    )


@router.get("/inspection")
def vin_inspection_page(
    request: Request,
    vin: str | None = Query(default=None),
    listing_id: int | None = Query(default=None),
    refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    has_query = bool((vin or "").strip() or listing_id is not None or refresh)
    context = _template_context(request, current_user, inspection_seo_meta(has_query=has_query))
    listing = None
    if listing_id is not None:
        listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
        if listing and listing.status != ListingStatus.published:
            if current_user is None or current_user.role != UserRole.admin:
                listing = None

    vin_input = (vin or (listing.vin if listing and listing.vin else "") or "").strip().upper()
    normalized_vin = _normalize_vin(vin_input)
    vin_error = None
    vin_report = None
    customs_result = None
    if normalized_vin:
        if not _vin_is_valid(normalized_vin):
            vin_error = "Некорректный VIN. Используй 17 символов без I, O, Q."
        else:
            try:
                customs_result = lookup_customs_vin(db, normalized_vin, force_refresh=refresh)
                vin_report = report_rows(customs_result)
            except CustomsVinError as exc:
                vin_error = str(exc)

    context["listing"] = listing
    context["vin"] = vin_input
    context["vin_error"] = vin_error
    context["vin_report"] = vin_report
    context["customs_result"] = customs_result
    return templates.TemplateResponse(request, "inspection.html", context)


@router.get("/catalog")
def catalog(
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    query, exact_hp, with_listings = _catalog_items_base_query(db, request)
    listing_pairs = _published_listing_make_models(db) if with_listings else None
    rows = query.filter(CatalogItem.make.isnot(None)).order_by(CatalogItem.make.asc(), CatalogItem.created_at.desc()).all()
    grouped: dict[str, dict] = {}
    for item in rows:
        make = (item.make or "").strip()
        if not make:
            continue
        if make not in grouped:
            grouped[make] = {
                "make": make,
                "count": 0,
                "first_id": item.id,
                "year_from": item.year_from,
                "year_to": item.year_to,
            }
        grouped[make]["count"] += 1
        if grouped[make]["year_from"] is None or (item.year_from is not None and item.year_from < grouped[make]["year_from"]):
            grouped[make]["year_from"] = item.year_from
        if grouped[make]["year_to"] is None or (item.year_to is not None and item.year_to > grouped[make]["year_to"]):
            grouped[make]["year_to"] = item.year_to

    makes = sorted(grouped.values(), key=lambda m: m["make"])
    if listing_pairs is not None:
        makes = [
            make_row
            for make_row in makes
            if any(pair[0] == normalize_match_text(make_row["make"]) for pair in listing_pairs)
        ]
    filter_pairs = _catalog_filter_query_pairs(request, exclude=_CATALOG_NAV_EXCLUDE)
    for make_row in makes:
        make_row["models_url"] = _build_catalog_filtered_url(
            "/catalog/models",
            [("make", make_row["make"]), *filter_pairs],
        )
        make_row["logo_url"] = _make_logo_url(make_row["make"])

    context = _template_context(request, current_user)
    context["makes"] = makes
    context["total"] = len(makes)
    context["catalog_filters_action"] = "/catalog"
    context["filters_reset_url"] = "/catalog"
    context["switch_to_models_url"] = _build_catalog_filtered_url(
        "/catalog/models",
        _catalog_filter_query_pairs(request, exclude=_CATALOG_NAV_EXCLUDE),
    )
    context["catalog_filter_query"] = urlencode(
        _catalog_filter_query_pairs(request, exclude=_CATALOG_NAV_EXCLUDE)
    )
    context["catalog_sidebar"] = _catalog_sidebar_payload(request, db)
    return templates.TemplateResponse(request, "catalog.html", context)


@router.get("/catalog/models")
def catalog_models(
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    selected_makes = [m.strip() for m in request.query_params.getlist("make") if m.strip()]
    make = selected_makes[0] if len(selected_makes) == 1 else None
    query, exact_hp, with_listings = _catalog_items_base_query(db, request)
    listing_pairs = _published_listing_make_models(db) if with_listings else None
    query = query.filter(CatalogItem.model.isnot(None))
    if selected_makes:
        query = query.filter(CatalogItem.make.in_(selected_makes))
    rows = query.order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.created_at.desc()).all()
    grouped: dict[str, dict] = {}
    for item in rows:
        make_name = (item.make or "").strip()
        if not make_name:
            continue
        canonical_model = _canonical_model_name(item.model)
        if not canonical_model:
            continue
        group_key = f"{make_name}|||{canonical_model}"
        if group_key not in grouped:
            grouped[group_key] = {
                "make": make_name,
                "model": canonical_model,
                "count": 0,
                "first_id": item.id,
                "year_from": item.year_from,
                "year_to": item.year_to,
                "generations": set(),
                "generation_cards": {},
            }
        grouped[group_key]["count"] += 1
        if item.generation:
            grouped[group_key]["generations"].add(item.generation)
            generation_key = item.generation
            cards = grouped[group_key]["generation_cards"]
            if generation_key not in cards:
                cards[generation_key] = {
                    "generation": generation_key,
                    "count": 0,
                    "first_id": item.id,
                    "year_from": item.year_from,
                    "year_to": item.year_to,
                    "make": make_name,
                    "model": canonical_model,
                    "rating": None,
                }
            cards[generation_key]["count"] += 1
            _apply_group_rating(cards[generation_key], item)
            if cards[generation_key]["year_from"] is None or (
                item.year_from is not None and item.year_from < cards[generation_key]["year_from"]
            ):
                cards[generation_key]["year_from"] = item.year_from
            if cards[generation_key]["year_to"] is None or (
                item.year_to is not None and item.year_to > cards[generation_key]["year_to"]
            ):
                cards[generation_key]["year_to"] = item.year_to
        if grouped[group_key]["year_from"] is None or (
            item.year_from is not None and item.year_from < grouped[group_key]["year_from"]
        ):
            grouped[group_key]["year_from"] = item.year_from
        if grouped[group_key]["year_to"] is None or (
            item.year_to is not None and item.year_to > grouped[group_key]["year_to"]
        ):
            grouped[group_key]["year_to"] = item.year_to

    models = sorted(grouped.values(), key=lambda m: (m["make"], m["model"]))
    if listing_pairs is not None:
        models = [
            model_row
            for model_row in models
            if (normalize_match_text(model_row["make"]), _canonical_model_name(model_row["model"])) in listing_pairs
        ]
    filter_pairs = _catalog_filter_query_pairs(request, exclude=_CATALOG_NAV_EXCLUDE)
    generation_preview_ids: list[int] = []
    for model_item in models:
        model_item["generation_count"] = len(model_item["generations"])
        gen_pairs = [
            ("make", model_item["make"]),
            ("model", model_item["model"]),
            *filter_pairs,
        ]
        model_item["generations_url"] = _build_catalog_filtered_url("/catalog/generations", gen_pairs)
        model_item["listings_url"] = _build_listings_url(
            brand=model_item["make"],
            model=model_item["model"],
            year_from=model_item.get("year_from"),
            year_to=model_item.get("year_to"),
        )
        generation_cards = list(model_item["generation_cards"].values())
        generation_cards.sort(key=lambda g: (g["count"], g["year_to"] or 0, g["year_from"] or 0), reverse=True)
        for generation_card in generation_cards:
            params = [
                ("make", generation_card["make"]),
                ("model", generation_card["model"]),
                ("generation", generation_card["generation"]),
                *filter_pairs,
            ]
            generation_card["mods_url"] = _build_catalog_filtered_url("/catalog/modifications", params)
        model_item["generation_previews"] = generation_cards[:3]
        generation_preview_ids.extend([g["first_id"] for g in model_item["generation_previews"]])

    context = _template_context(
        request,
        current_user,
        catalog_models_seo_meta(make, total=len(models)),
    )
    if exact_hp or with_listings or not make:
        context["seo_noindex"] = True
    context["make"] = make
    context["selected_makes"] = selected_makes
    context["models"] = models
    context["cover_urls"] = _build_cover_url_map([item["first_id"] for item in models], db)
    context["generation_cover_urls"] = _build_cover_url_map(generation_preview_ids, db)
    context["total"] = len(models)
    context["catalog_filters_action"] = _build_catalog_filtered_url(
        "/catalog/models",
        _catalog_filter_query_pairs(request, exclude=frozenset({"model", "generation"})),
    )
    context["filters_reset_url"] = _build_catalog_filtered_url(
        "/catalog/models",
        [("make", make_name) for make_name in selected_makes],
    )
    context["switch_to_makes_url"] = _build_catalog_filtered_url(
        "/catalog",
        _catalog_filter_query_pairs(request, exclude=_CATALOG_NAV_EXCLUDE),
    )
    context["preserve_makes"] = selected_makes
    context["catalog_sidebar"] = _catalog_sidebar_payload(request, db)
    return templates.TemplateResponse(request, "catalog_models.html", context)


@router.get("/catalog/generations")
def catalog_generations(
    request: Request,
    make: str | None = Query(default=None),
    model: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    canonical_model = _canonical_model_name(model) if model else ""
    query, exact_hp, with_listings = _catalog_items_base_query(db, request)
    listing_pairs = _published_listing_make_models(db) if with_listings else None
    if make:
        query = query.filter(CatalogItem.make == make)
    if canonical_model:
        query = query.filter(CatalogItem.model == canonical_model)
    rows = query.order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.year_from.desc()).all()
    grouped: dict[str, dict] = {}
    for item in rows:
        make_name = (item.make or "").strip()
        model_name = _canonical_model_name(item.model)
        if not make_name or not model_name:
            continue
        generation_name = item.generation or "Без поколения"
        group_key = f"{make_name}|||{model_name}|||{generation_name}"
        if group_key not in grouped:
            grouped[group_key] = {
                "make": make_name,
                "model": model_name,
                "generation": generation_name,
                "count": 0,
                "first_id": item.id,
                "year_from": item.year_from,
                "year_to": item.year_to,
                "rating": None,
            }
        grouped[group_key]["count"] += 1
        _apply_group_rating(grouped[group_key], item)
        if grouped[group_key]["year_from"] is None or (
            item.year_from is not None and item.year_from < grouped[group_key]["year_from"]
        ):
            grouped[group_key]["year_from"] = item.year_from
        if grouped[group_key]["year_to"] is None or (
            item.year_to is not None and item.year_to > grouped[group_key]["year_to"]
        ):
            grouped[group_key]["year_to"] = item.year_to

    generations = sorted(
        grouped.values(),
        key=lambda g: (g["make"], g["model"], -(g["year_from"] or 0), g["generation"]),
    )
    if listing_pairs is not None:
        generations = [
            generation_row
            for generation_row in generations
            if (
                normalize_match_text(generation_row["make"]),
                _canonical_model_name(generation_row["model"]),
            )
            in listing_pairs
        ]
    filter_pairs = _catalog_filter_query_pairs(request, exclude=_CATALOG_NAV_EXCLUDE)
    for generation_item in generations:
        params = [
            ("make", generation_item["make"]),
            ("model", generation_item["model"]),
            *filter_pairs,
        ]
        if generation_item["generation"] != "Без поколения":
            params.append(("generation", generation_item["generation"]))
        generation_item["mods_url"] = _build_catalog_filtered_url("/catalog/modifications", params)
        generation_item["listings_url"] = _build_listings_url(
            brand=generation_item["make"],
            model=generation_item["model"],
            year_from=generation_item.get("year_from"),
            year_to=generation_item.get("year_to"),
        )

    context = _template_context(
        request,
        current_user,
        catalog_generations_seo_meta(make, canonical_model or None, total=len(generations)),
    )
    if exact_hp or with_listings or not (make and canonical_model):
        context["seo_noindex"] = True
    context["make"] = make
    context["model"] = canonical_model
    context["generations"] = generations
    context["cover_urls"] = _build_cover_url_map([item["first_id"] for item in generations], db)
    context["total"] = len(generations)
    context["back_to_models_url"] = _build_catalog_filtered_url(
        "/catalog/models",
        [("make", make), *_catalog_filter_query_pairs(request, exclude=frozenset({"model", "generation"}))],
    ) if make else _build_catalog_filtered_url(
        "/catalog/models",
        _catalog_filter_query_pairs(request, exclude=frozenset({"model", "generation"})),
    )
    reset_pairs: list[tuple[str, str]] = []
    if make:
        reset_pairs.append(("make", make))
    if canonical_model:
        reset_pairs.append(("model", canonical_model))
    context["catalog_filters_action"] = _build_catalog_filtered_url(
        "/catalog/generations",
        _catalog_filter_query_pairs(request, exclude=frozenset({"generation"})),
    )
    context["filters_reset_url"] = _build_catalog_filtered_url("/catalog/generations", reset_pairs)
    context["preserve_makes"] = [make] if make else []
    context["preserve_model"] = canonical_model or ""
    context["catalog_sidebar"] = _catalog_sidebar_payload(request, db)
    return templates.TemplateResponse(request, "catalog_generations.html", context)


@router.get("/catalog/modifications")
def catalog_modifications(
    request: Request,
    body_type: str | None = Query(default=None),
    export_country: str | None = Query(default=None),
    fuel_type: str | None = Query(default=None),
    transmission: str | None = Query(default=None),
    year_from: str | None = Query(default=None),
    year_to: str | None = Query(default=None),
    exact_hp: bool = Query(default=False),
    sort: str = Query(default="year_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    vehicle_rows = _parse_vehicle_filter_rows(request.query_params)
    primary_row = vehicle_rows[0] if vehicle_rows else {"make": "", "model": "", "generation": ""}
    make = primary_row.get("make") or None
    model = primary_row.get("model") or None
    generation = primary_row.get("generation") or None
    parsed_year_from = _parse_optional_year(year_from)
    parsed_year_to = _parse_optional_year(year_to)
    body_type = normalize_body_type_label(body_type) if body_type else None
    fuel_type = normalize_fuel_type_label(fuel_type) if fuel_type else None
    query = _apply_hp_filter(db.query(CatalogItem), exact_hp=exact_hp)
    query = _apply_catalog_item_filters(
        query=query,
        db=db,
        vehicle_rows=vehicle_rows,
        body_type=body_type,
        export_country=export_country,
        fuel_type=fuel_type,
        transmission=transmission,
        parsed_year_from=parsed_year_from,
        parsed_year_to=parsed_year_to,
    )
    query = query.filter(CatalogItem.source_site == "av.by")
    # If enriched source exists for selected generation, hide legacy duplicates.
    if make and model and generation:
        canonical_model = _canonical_model_name(model)
        has_enriched = (
            db.query(CatalogItem.id)
            .filter(
                CatalogItem.make == make,
                CatalogItem.model == canonical_model,
                CatalogItem.generation == generation,
                CatalogItem.source_site == "av.by",
            )
            .first()
            is not None
        )
        if has_enriched:
            query = query.filter(CatalogItem.source_site == "av.by")

    avby_first = case((CatalogItem.source_site == "av.by", 0), else_=1)
    if sort == "price_asc":
        query = query.order_by(avby_first, CatalogItem.min_price_rub.asc(), CatalogItem.created_at.desc())
    elif sort == "price_desc":
        query = query.order_by(avby_first, CatalogItem.min_price_rub.desc(), CatalogItem.created_at.desc())
    elif sort == "year_asc":
        query = query.order_by(avby_first, CatalogItem.year_from.asc(), CatalogItem.created_at.desc())
    elif sort == "year_desc":
        query = query.order_by(avby_first, CatalogItem.year_from.desc(), CatalogItem.created_at.desc())
    else:
        query = query.order_by(avby_first, desc(CatalogItem.created_at))

    deduped_items = _dedupe_modifications(query.all())
    total = len(deduped_items)
    generation_rating = next((item.rating for item in deduped_items if item.rating is not None), None)
    offset = (page - 1) * page_size
    items = deduped_items[offset : offset + page_size]
    extra_filters = bool(
        body_type
        or export_country
        or fuel_type
        or transmission
        or parsed_year_from is not None
        or parsed_year_to is not None
        or exact_hp
        or sort not in ("", "year_desc")
        or page > 1
        or page_size != 20
        or len(vehicle_rows) > 1
    )
    context = _template_context(
        request,
        current_user,
        catalog_modifications_seo_meta(
            make, model, generation, total=total, extra_filters=extra_filters
        ),
    )
    context["items"] = items
    context["generation_rating"] = float(generation_rating) if generation_rating is not None else None
    context["mod_titles"] = _build_modification_titles(items)
    context["mod_table_groups"] = _build_modification_table_groups(items)
    context["generation_years"] = _catalog_items_year_range(deduped_items)
    context["total"] = total
    context["page"] = page
    context["page_size"] = page_size
    context["total_pages"] = max(1, (total + page_size - 1) // page_size)
    context["has_prev"] = page > 1
    context["has_next"] = offset + len(items) < total
    context["filters"] = {
        "vehicle_rows": vehicle_rows,
        "make": make or "",
        "model": model or "",
        "generation": generation or "",
        "body_type": normalize_body_type_label(body_type) or "" if body_type else "",
        "export_country": export_country or "",
        "fuel_type": fuel_type or "",
        "transmission": transmission or "",
        "year_from": parsed_year_from if parsed_year_from is not None else "",
        "year_to": parsed_year_to if parsed_year_to is not None else "",
        "exact_hp": exact_hp,
        "sort": sort,
    }

    def build_page_url(page_num: int) -> str:
        pairs = _vehicle_rows_to_query_pairs(vehicle_rows, make_key="make", model_key="model", generation_key="generation")
        if body_type:
            pairs.append(("body_type", body_type))
        if export_country:
            pairs.append(("export_country", export_country))
        if fuel_type:
            pairs.append(("fuel_type", fuel_type))
        if transmission:
            pairs.append(("transmission", transmission))
        if parsed_year_from is not None:
            pairs.append(("year_from", str(parsed_year_from)))
        if parsed_year_to is not None:
            pairs.append(("year_to", str(parsed_year_to)))
        if exact_hp:
            pairs.append(("exact_hp", "1"))
        if sort:
            pairs.append(("sort", sort))
        if page_size != 20:
            pairs.append(("page_size", str(page_size)))
        pairs.append(("page", str(page_num)))
        return "/catalog/modifications?" + urlencode(pairs)

    context["prev_url"] = build_page_url(page - 1) if context["has_prev"] else None
    context["next_url"] = build_page_url(page + 1) if context["has_next"] else None
    context["back_to_catalog_url"] = "/catalog/generations?" + urlencode(
        {k: v for k, v in {"make": make or None, "model": _canonical_model_name(model or "") or None}.items() if v}
    )
    ad_listings: list[CarListing] = []
    ad_listing_mod_names: dict[int, str] = {}
    generation_items: list[CatalogItem] = []
    canonical_model = _canonical_model_name(model or "")
    if make and canonical_model and generation and generation != "Без поколения":
        generation_items_query = _apply_hp_filter(
            db.query(CatalogItem).filter(
                CatalogItem.source_site == "av.by",
                CatalogItem.make == make,
                CatalogItem.model == canonical_model,
                CatalogItem.generation == generation,
            ),
            exact_hp=exact_hp,
        )
        generation_items = generation_items_query.all()
        items_by_id = {item.id: item for item in generation_items}
        if generation_items:
            listings_by_item = fetch_listings_for_catalog_items(db, generation_items, limit_per_item=8)
            seen_ids: set[int] = set()
            for item in generation_items:
                mod_name = _modification_display_name(item)
                for listing in listings_by_item.get(item.id, []):
                    if listing.id in seen_ids:
                        continue
                    seen_ids.add(listing.id)
                    ad_listings.append(listing)
                    if mod_name:
                        ad_listing_mod_names[listing.id] = mod_name
                    if len(ad_listings) >= 8:
                        break
                if len(ad_listings) >= 8:
                    break
            if not ad_listings:
                year_from_values = [row.year_from for row in generation_items if row.year_from is not None]
                year_to_values = [row.year_to for row in generation_items if row.year_to is not None]
                generation_year_from = min(year_from_values) if year_from_values else None
                generation_year_to = max(year_to_values) if year_to_values else None
                listings_query = db.query(CarListing).filter(
                    CarListing.status == ListingStatus.published,
                    CarListing.brand.ilike(make),
                    CarListing.model.ilike(canonical_model),
                )
                if generation_year_from is not None:
                    listings_query = listings_query.filter(CarListing.year >= generation_year_from)
                if generation_year_to is not None:
                    listings_query = listings_query.filter(CarListing.year <= generation_year_to)
                ad_listings = listings_query.order_by(CarListing.created_at.desc()).limit(8).all()
        for listing in ad_listings:
            if listing.id in ad_listing_mod_names:
                continue
            linked_item = items_by_id.get(listing.catalog_item_id) if listing.catalog_item_id else None
            if linked_item is None and listing.catalog_item_id:
                linked_item = db.get(CatalogItem, listing.catalog_item_id)
                if linked_item:
                    items_by_id[linked_item.id] = linked_item
            if linked_item:
                mod_name = _modification_display_name(linked_item)
                if mod_name:
                    ad_listing_mod_names[listing.id] = mod_name
    context["ad_listings"] = ad_listings
    context["ad_listing_mod_names"] = ad_listing_mod_names
    context["ad_listing_cover_urls"] = _build_listing_catalog_cover_urls(ad_listings, generation_items, db)
    listings_all_url = None
    if make and canonical_model and generation and generation != "Без поколения":
        year_from_values = [row.year_from for row in generation_items if row.year_from is not None]
        year_to_values = [row.year_to for row in generation_items if row.year_to is not None]
        listings_all_url = _build_listings_url(
            brand=make,
            model=canonical_model,
            year_from=min(year_from_values) if year_from_values else None,
            year_to=max(year_to_values) if year_to_values else None,
        )
    context["listings_all_url"] = listings_all_url
    context["catalog_filters_action"] = _build_catalog_filtered_url(
        "/catalog/modifications",
        _catalog_filter_query_pairs(request),
    )
    context["filters_reset_url"] = "/catalog/modifications"
    context["catalog_sidebar"] = _catalog_sidebar_payload(request, db)
    return templates.TemplateResponse(request, "catalog_modifications.html", context)


@router.get("/catalog/item/{item_id}")
def catalog_item_detail(request: Request, item_id: int, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    item = db.query(CatalogItem).filter(CatalogItem.id == item_id).first()
    if not item or (item.engine_power_hp is not None and item.engine_power_hp > 160):
        context = _template_context(
            request,
            _resolve_user_from_request(request, db),
            SeoMeta(
                title="Комплектация не найдена — Auto160",
                description="Позиция каталога не найдена или не подходит под фильтр до 160 л.с.",
                path=f"/catalog/item/{item_id}",
                noindex=True,
            ),
        )
        context["item"] = None
        context["photos"] = []
        return templates.TemplateResponse(
            request, "catalog_item_detail.html", context, status_code=404
        )

    photos = (
        db.query(CatalogItemPhoto)
        .filter(CatalogItemPhoto.catalog_item_id == item_id)
        .order_by(CatalogItemPhoto.is_cover.desc(), CatalogItemPhoto.sort_order.asc(), CatalogItemPhoto.id.asc())
        .all()
    )
    photo_urls = [build_app_download_url(photo.storage_key) for photo in photos]
    if not photo_urls:
        listings_cache = _fetch_listings_for_catalog_items([item], db)
        resolved_cover = _resolve_catalog_item_cover(item, listings_cache)
        raw_urls = _extract_photo_urls_from_raw_specs(item.raw_specs or {})
        if resolved_cover and resolved_cover not in raw_urls:
            photo_urls = [resolved_cover, *raw_urls]
        elif raw_urls:
            photo_urls = raw_urls
        elif resolved_cover:
            photo_urls = [resolved_cover]
    photo_urls = [normalize_display_image_url(url) or url for url in photo_urls]
    cover_url = photo_urls[0] if photo_urls else None
    context = _template_context(
        request,
        current_user,
        catalog_item_seo_meta(item, cover_url=cover_url, base=site_base_url(request)),
    )
    context["item"] = item
    context["photos"] = photo_urls
    spec_rows = _resolve_best_spec_rows(item, db)
    context["spec_rows"] = spec_rows
    context["spec_sections"] = _group_spec_rows(spec_rows)
    context["listings_url"] = _build_listings_url(catalog_item_id=item.id)
    context["generation_listings_url"] = _generation_listings_url(db, item)
    related_listings = fetch_listings_for_catalog_items(db, [item], limit_per_item=8).get(item.id, [])
    context["related_listings"] = related_listings
    context["related_listing_cover_urls"] = _resolve_listing_cover_urls(related_listings, db)
    return templates.TemplateResponse(request, "catalog_item_detail.html", context)


@router.get("/catalog/compare")
def catalog_compare(
    request: Request,
    ids: list[int] = Query(default=[]),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    compare_seo = SeoMeta(
        title="Сравнение комплектаций — Auto160",
        description="Сравнение комплектаций автомобилей до 160 л.с.",
        path="/catalog/compare",
        noindex=True,
    )
    if not ids:
        context = _template_context(request, current_user, compare_seo)
        context["items"] = []
        context["rows"] = []
        return templates.TemplateResponse(request, "catalog_compare.html", context)

    unique_ids: list[int] = []
    seen: set[int] = set()
    for item_id in ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        unique_ids.append(item_id)

    found_items = db.query(CatalogItem).filter(CatalogItem.id.in_(unique_ids)).all()
    by_id = {item.id: item for item in found_items}
    items = [
        by_id[item_id]
        for item_id in unique_ids
        if item_id in by_id and (by_id[item_id].engine_power_hp is None or by_id[item_id].engine_power_hp <= 160)
    ]

    compare_maps = [_build_compare_value_map(item, db) for item in items]
    ordered_labels: list[str] = []
    for mapping in compare_maps:
        for label in mapping.keys():
            if label not in ordered_labels:
                ordered_labels.append(label)

    rows = [
        {
            "label": label,
            "values": [mapping.get(label, "—") for mapping in compare_maps],
            "classes": [],
        }
        for label in ordered_labels
    ]

    for row in rows:
        numeric_values = [_parse_numeric_value(v) for v in row["values"]]
        valid = [v for v in numeric_values if v is not None]
        if len(valid) < 2:
            row["classes"] = ["compare-neutral"] * len(row["values"])
            continue
        max_value = max(valid)
        min_value = min(valid)
        if max_value == min_value:
            row["classes"] = ["compare-neutral"] * len(row["values"])
            continue
        classes: list[str] = []
        for v in numeric_values:
            if v is None:
                classes.append("compare-neutral")
            elif v == max_value:
                classes.append("compare-better")
            elif v == min_value:
                classes.append("compare-worse")
            else:
                classes.append("compare-neutral")
        row["classes"] = classes

    grouped_rows: dict[str, list[dict]] = {}
    for row in rows:
        section = _section_for_label(row["label"])
        grouped_rows.setdefault(section, []).append(row)
    compare_sections: list[dict] = []
    for section_name, _ in SPEC_SECTIONS:
        section_rows = grouped_rows.get(section_name, [])
        if section_rows:
            compare_sections.append({"title": section_name, "rows": section_rows})
    if grouped_rows.get("Прочее"):
        compare_sections.append({"title": "Прочее", "rows": grouped_rows["Прочее"]})

    context = _template_context(request, current_user, compare_seo)
    context["items"] = items
    context["rows"] = rows
    context["compare_sections"] = compare_sections
    return templates.TemplateResponse(request, "catalog_compare.html", context)


@router.get("/guides/vin")
def guide_vin_page(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    context = _template_context(request, current_user, guide_vin_seo_meta(site_base_url(request)))
    return templates.TemplateResponse(request, "guide_vin.html", context)


@router.get("/guides/do-160-hp")
def guide_do_160_page(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    context = _template_context(request, current_user, guide_do_160_seo_meta(site_base_url(request)))
    return templates.TemplateResponse(request, "guide_do_160.html", context)


@router.get("/catalog/{listing_id}")
def catalog_item(request: Request, listing_id: int, db: Session = Depends(get_db)):
    return RedirectResponse(url=f"/listings/{listing_id}", status_code=302)


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "login.html", _template_context(request, current_user))


@router.get("/register")
def register_page(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "register.html", _template_context(request, current_user))


@router.get("/create-listing")
def create_listing_page(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "create_listing.html", _template_context(request, current_user))


@router.get("/profile/my-listings")
def profile_my_listings(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)
    listings = db.query(CatalogItem).order_by(desc(CatalogItem.created_at)).all()
    context = _template_context(request, current_user)
    context["listings"] = listings
    context["cover_urls"] = _build_cover_url_map([item.id for item in listings], db)
    return templates.TemplateResponse(request, "profile_listings.html", context)


@router.get("/admin/catalog/{item_id}/photos")
def admin_catalog_item_photos(request: Request, item_id: int, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)

    item = db.query(CatalogItem).filter(CatalogItem.id == item_id).first()
    if not item:
        return RedirectResponse(url="/profile/my-listings", status_code=302)

    photos = (
        db.query(CatalogItemPhoto)
        .filter(CatalogItemPhoto.catalog_item_id == item_id)
        .order_by(CatalogItemPhoto.is_cover.desc(), CatalogItemPhoto.sort_order.asc(), CatalogItemPhoto.id.asc())
        .all()
    )
    photo_cards = [
        {
            "id": p.id,
            "is_cover": p.is_cover,
            "sort_order": p.sort_order,
            "content_type": p.content_type,
            "file_url": build_app_download_url(p.storage_key),
        }
        for p in photos
    ]

    context = _template_context(request, current_user)
    context["item"] = item
    context["photos"] = photo_cards
    return templates.TemplateResponse(request, "admin_catalog_photos.html", context)


@router.get("/admin/users")
def admin_users_page(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)
    users = db.query(User).order_by(User.created_at.desc()).all()
    context = _template_context(request, current_user)
    context["users"] = users
    return templates.TemplateResponse(request, "admin_users.html", context)


@router.get("/admin/ratings")
def admin_ratings_page(
    request: Request,
    q: str = Query(default=""),
    make: str = Query(default=""),
    status: str = Query(default="all"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)

    status_filter = status if status in {"all", "rated", "unrated"} else "all"
    per_page = DEFAULT_PAGE_SIZE
    rows, total = list_generation_ratings(
        db,
        make=make,
        q=q,
        status=status_filter,
        page=page,
        per_page=per_page,
    )
    total_pages = max((total + per_page - 1) // per_page, 1)
    if page > total_pages:
        page = total_pages
        rows, total = list_generation_ratings(
            db,
            make=make,
            q=q,
            status=status_filter,
            page=page,
            per_page=per_page,
        )

    def _ratings_url(**overrides) -> str:
        params = {
            "q": q.strip(),
            "make": make.strip(),
            "status": status_filter,
            "page": page,
        }
        params.update(overrides)
        pairs = []
        if params["q"]:
            pairs.append(("q", params["q"]))
        if params["make"]:
            pairs.append(("make", params["make"]))
        if params["status"] != "all":
            pairs.append(("status", params["status"]))
        if int(params["page"] or 1) > 1:
            pairs.append(("page", str(params["page"])))
        query = urlencode(pairs)
        return "/admin/ratings" + (f"?{query}" if query else "")

    context = _template_context(request, current_user)
    context.update(
        {
            "rating_rows": rows,
            "rating_total": total,
            "rating_page": page,
            "rating_total_pages": total_pages,
            "rating_has_prev": page > 1,
            "rating_has_next": page < total_pages,
            "rating_prev_url": _ratings_url(page=page - 1) if page > 1 else None,
            "rating_next_url": _ratings_url(page=page + 1) if page < total_pages else None,
            "rating_q": q.strip(),
            "rating_make": make.strip(),
            "rating_status": status_filter,
            "rating_makes": list_catalog_makes(db),
            "rating_choices": RATING_CHOICES,
            "format_rating": format_rating,
            "rating_filter_urls": {
                "all": _ratings_url(status="all", page=1),
                "rated": _ratings_url(status="rated", page=1),
                "unrated": _ratings_url(status="unrated", page=1),
            },
        }
    )
    return templates.TemplateResponse(request, "admin_ratings.html", context)


def _format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds} сек"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} мин {sec} сек"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} ч {minutes} мин"


AVBY_SYNC_TRIGGER_LABELS = {
    "scheduler": "Планировщик",
    "manual": "Вручную",
    "admin": "Админ",
}

AVBY_SYNC_STATUS_LABELS = {
    "running": "В процессе",
    "success": "Успех",
    "failed": "Ошибка",
}


@router.get("/admin/avby-sync")
def admin_avby_sync_page(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)

    runs = db.query(AvbySyncRun).order_by(desc(AvbySyncRun.started_at)).limit(50).all()
    avby_filter = CarListing.avby_id.isnot(None)

    avby_total = db.query(CarListing).filter(avby_filter).count()
    avby_published = (
        db.query(CarListing)
        .filter(avby_filter, CarListing.status == ListingStatus.published)
        .count()
    )
    avby_archived = (
        db.query(CarListing)
        .filter(avby_filter, CarListing.status == ListingStatus.archived)
        .count()
    )
    catalog_models = (
        db.query(CatalogItem)
        .filter(CatalogItem.source_site == "av.by")
        .count()
    )

    last_run = runs[0] if runs else None
    last_success = (
        db.query(AvbySyncRun)
        .filter(AvbySyncRun.status == "success")
        .order_by(desc(AvbySyncRun.started_at))
        .first()
    )
    running_sync = (
        db.query(AvbySyncRun)
        .filter(AvbySyncRun.status == "running")
        .order_by(desc(AvbySyncRun.started_at))
        .first()
    )

    since_24h = datetime.utcnow() - timedelta(hours=24)
    recent_success_runs = (
        db.query(AvbySyncRun)
        .filter(AvbySyncRun.started_at >= since_24h, AvbySyncRun.status == "success")
        .all()
    )
    created_24h = sum(run.created_count for run in recent_success_runs)
    updated_24h = sum(run.updated_count for run in recent_success_runs)
    pages_24h = sum(run.pages_fetched_count for run in recent_success_runs)
    syncs_24h = len(recent_success_runs)

    run_ids = [run.id for run in runs]
    vin_checks_by_run: dict[int, list[AvbySyncRunVinCheck]] = {}
    if run_ids:
        vin_check_rows = (
            db.query(AvbySyncRunVinCheck)
            .filter(AvbySyncRunVinCheck.sync_run_id.in_(run_ids))
            .all()
        )
        for row in vin_check_rows:
            vin_checks_by_run.setdefault(row.sync_run_id, []).append(row)

    run_rows = []
    for run in runs:
        duration_sec = None
        if run.started_at and run.finished_at:
            duration_sec = int((run.finished_at - run.started_at).total_seconds())
        vin_summary = summarize_sync_run_vin_checks(vin_checks_by_run.get(run.id, []))
        run_rows.append(
            {
                "run": run,
                "duration": _format_duration(duration_sec),
                "trigger_label": AVBY_SYNC_TRIGGER_LABELS.get(run.trigger, run.trigger),
                "status_label": AVBY_SYNC_STATUS_LABELS.get(run.status, run.status),
                "vin_summary": vin_summary,
            }
        )

    last_run_duration = None
    if last_run and last_run.started_at and last_run.finished_at:
        last_run_duration = _format_duration(
            int((last_run.finished_at - last_run.started_at).total_seconds())
        )

    context = _template_context(request, current_user)
    context.update(
        {
            "runs": run_rows,
            "avby_total": avby_total,
            "avby_published": avby_published,
            "avby_archived": avby_archived,
            "catalog_models": catalog_models,
            "last_run": last_run,
            "last_run_duration": last_run_duration,
            "last_success": last_success,
            "running_sync": running_sync,
            "created_24h": created_24h,
            "updated_24h": updated_24h,
            "pages_24h": pages_24h,
            "syncs_24h": syncs_24h,
            "trigger_labels": AVBY_SYNC_TRIGGER_LABELS,
            "status_labels": AVBY_SYNC_STATUS_LABELS,
        }
    )
    return templates.TemplateResponse(request, "admin_avby_sync.html", context)


@router.get("/admin/avby-sync/{run_id}")
def admin_avby_sync_run_page(request: Request, run_id: int, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)

    run = db.query(AvbySyncRun).filter(AvbySyncRun.id == run_id).first()
    if run is None:
        return RedirectResponse(url="/admin/avby-sync", status_code=302)

    checks = (
        db.query(AvbySyncRunVinCheck)
        .filter(AvbySyncRunVinCheck.sync_run_id == run_id)
        .order_by(AvbySyncRunVinCheck.id.asc())
        .all()
    )
    listing_ids = {check.listing_id for check in checks}
    listings_by_id: dict[int, CarListing] = {}
    if listing_ids:
        listings_by_id = {
            listing.id: listing
            for listing in db.query(CarListing).filter(CarListing.id.in_(listing_ids)).all()
        }

    check_rows = []
    for check in checks:
        listing = listings_by_id.get(check.listing_id)
        check_rows.append(
            {
                "check": check,
                "listing": listing,
                "phase_label": PHASE_LABELS.get(check.phase, check.phase),
            }
        )

    duration_sec = None
    if run.started_at and run.finished_at:
        duration_sec = int((run.finished_at - run.started_at).total_seconds())

    context = _template_context(request, current_user)
    context.update(
        {
            "run": run,
            "run_duration": _format_duration(duration_sec),
            "trigger_label": AVBY_SYNC_TRIGGER_LABELS.get(run.trigger, run.trigger),
            "status_label": AVBY_SYNC_STATUS_LABELS.get(run.status, run.status),
            "vin_summary": summarize_sync_run_vin_checks(checks),
            "check_rows": check_rows,
            "trigger_labels": AVBY_SYNC_TRIGGER_LABELS,
            "status_labels": AVBY_SYNC_STATUS_LABELS,
        }
    )
    return templates.TemplateResponse(request, "admin_avby_sync_run.html", context)


AVBY_ACCOUNT_STATUS_LABELS = {
    "confirmed": "Подтверждён",
    "phone_verified": "Телефон OK",
    "failed": "Ошибка",
    "mailtm_only": "Только почта",
    "pending": "Ожидает",
}

AVBY_ACCOUNT_PURPOSE_LABELS = {
    "parser": "Парсер",
    "vin_test": "VIN",
}


@router.get("/admin/avby-accounts")
def admin_avby_accounts_page(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)

    rows = db.query(AvbyServiceAccount).order_by(AvbyServiceAccount.created_at.desc()).all()
    accounts = []
    for account in rows:
        item = serialize_account_public(account)
        item["registered_at"] = account.registered_at
        item["created_at"] = account.created_at
        accounts.append(item)

    confirmed = sum(1 for row in rows if row.status in {"confirmed", "phone_verified"})
    vin_pool = list_active_vin_accounts(db)
    context = _template_context(request, current_user)
    context.update(
        {
            "accounts": accounts,
            "json_path": settings.avby_accounts_json_path,
            "status_labels": AVBY_ACCOUNT_STATUS_LABELS,
            "purpose_labels": AVBY_ACCOUNT_PURPOSE_LABELS,
            "stats": {
                "total": len(rows),
                "confirmed": confirmed,
                "with_api_key": sum(1 for row in rows if row.api_key),
                "active": sum(1 for row in rows if row.is_active),
                "vin_rotation": len(vin_pool),
                "failed": sum(1 for row in rows if row.status == "failed"),
            },
        }
    )
    return templates.TemplateResponse(request, "admin_avby_accounts.html", context)


@router.get("/admin/analytics")
def admin_analytics_page(
    request: Request,
    tab: str = Query(default="traffic"),
    days: int = Query(default=7, ge=1, le=90),
    page: int = Query(default=1, ge=1),
    sort: str = Query(default="dates"),
    dir: str = Query(default="desc"),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)

    active_tab = "vin" if tab == "vin" else "traffic"
    context = _template_context(request, current_user)
    context.update(
        {
            "active_tab": active_tab,
            "days": days,
            "day_options": [1, 7, 14, 30],
            "event_labels": EVENT_LABELS,
            "refresh_seconds": 30,
        }
    )

    if active_tab == "vin":
        per_page = 50
        vin_sort = VinListingSort(sort=sort, direction=dir).normalized()
        vin_rows, vin_total = build_vin_listings_report(
            db,
            page=page,
            per_page=per_page,
            sort=vin_sort,
        )
        total_pages = max((vin_total + per_page - 1) // per_page, 1)
        if page > total_pages:
            page = total_pages
            vin_rows, vin_total = build_vin_listings_report(
                db,
                page=page,
                per_page=per_page,
                sort=vin_sort,
            )
        context.update(
            {
                "vin_rows": vin_rows,
                "vin_total": vin_total,
                "vin_page": page,
                "vin_total_pages": total_pages,
                "vin_has_prev": page > 1,
                "vin_has_next": page < total_pages,
                "vin_sort": vin_sort,
                "vin_sort_columns": SORT_COLUMNS,
                "vin_sort_urls": {
                    column: f"/admin/analytics?{vin_sort.toggle_url(column)}"
                    for column in SORT_COLUMNS
                },
                "vin_prev_url": f"/admin/analytics?{vin_sort.query_string(page=page - 1)}" if page > 1 else None,
                "vin_next_url": f"/admin/analytics?{vin_sort.query_string(page=page + 1)}" if page < total_pages else None,
            }
        )
    else:
        summary = build_analytics_summary(db, days=days)
        context.update(summary)

    return templates.TemplateResponse(request, "admin_analytics.html", context)


@router.get("/admin/logs")
def admin_logs_page(
    request: Request,
    service: str = Query(default="api"),
    lines: int = Query(default=200, ge=10, le=2000),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.role != UserRole.admin:
        return RedirectResponse(url="/", status_code=302)

    if service not in LOG_SERVICES:
        service = "api"
    content, path = tail_log(service, lines=lines)

    services = [{"id": service_id, "label": LOG_SERVICE_LABELS[service_id]} for service_id in LOG_SERVICES]
    context = _template_context(request, current_user)
    context.update(
        {
            "service": service,
            "lines": lines,
            "line_options": [100, 200, 500, 1000],
            "services": services,
            "log_content": content,
            "log_path": str(path) if path else None,
            "log_dir": str(log_dir()),
            "log_timezone": str(log_timezone()),
            "refresh_seconds": 5,
            "fetched_at": format_log_time(),
        }
    )
    return templates.TemplateResponse(request, "admin_logs.html", context)


@router.get("/logout")
def logout_page(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    if current_user:
        record_auth_event(request, current_user, "logout")
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response
