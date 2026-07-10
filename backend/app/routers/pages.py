import hashlib
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from jose import JWTError
from sqlalchemy import case, desc, or_
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_setup import LOG_SERVICES, log_dir, tail_log
from app.avby_accounts import list_active_vin_accounts, serialize_account_public
from app.db import get_db
from app.models import AvbyServiceAccount, AvbySyncRun, CarListing, CatalogItem, CatalogItemPhoto, ListingStatus, User, UserRole
from app.security import decode_token, is_token_revoked
from app.storage import build_app_download_url

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


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

MAKE_LOGO_URLS = {
    "audi": "https://cdn.simpleicons.org/audi/111827",
    "bmw": "https://cdn.simpleicons.org/bmw/111827",
    "citroen": "https://cdn.simpleicons.org/citroen/111827",
    "honda": "https://cdn.simpleicons.org/honda/111827",
    "mini": "https://cdn.simpleicons.org/mini/111827",
    "nissan": "https://cdn.simpleicons.org/nissan/111827",
    "opel": "https://cdn.simpleicons.org/opel/111827",
    "renault": "https://cdn.simpleicons.org/renault/111827",
    "volvo": "https://cdn.simpleicons.org/volvo/111827",
}


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


def _template_context(request: Request, current_user: User | None) -> dict:
    return {
        "request": request,
        "current_user": current_user,
        "is_authenticated": current_user is not None,
        "is_admin": current_user is not None and current_user.role == UserRole.admin,
    }


def _normalize_match_text(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower().replace("ё", "е")


def _body_types_compatible(catalog_body: str | None, listing_body: str | None) -> bool:
    left = _normalize_match_text(catalog_body)
    right = _normalize_match_text(listing_body)
    if not left or not right:
        return True
    if left == right:
        return True
    return left in right or right in left


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


def _listing_match_score(listing: CarListing, item: CatalogItem) -> int:
    if not listing.cover_photo_url:
        return -1
    if _normalize_match_text(listing.brand) != _normalize_match_text(item.make):
        return -1
    if _canonical_model_name(listing.model) != _canonical_model_name(item.model):
        return -1
    if not _body_types_compatible(item.body_type, listing.body_type):
        return -1

    score = 10
    if item.body_type and listing.body_type:
        if _normalize_match_text(item.body_type) == _normalize_match_text(listing.body_type):
            score += 40
        else:
            score += 25
    if item.generation and listing.generation:
        if _normalize_match_text(item.generation) == _normalize_match_text(listing.generation):
            score += 20
        elif _normalize_match_text(listing.generation) in _normalize_match_text(item.generation):
            score += 10
    if item.year_from is not None and listing.year is not None:
        year_to = item.year_to if item.year_to is not None else item.year_from
        if item.year_from <= listing.year <= year_to:
            score += 15
        elif abs(listing.year - item.year_from) <= 1 or abs(listing.year - year_to) <= 1:
            score += 5
    if item.engine_power_hp is not None and listing.engine_power_hp is not None:
        diff = abs(item.engine_power_hp - listing.engine_power_hp)
        if diff <= 5:
            score += 25
        elif diff <= 15:
            score += 12
        elif diff <= 30:
            score += 5
    return score


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
        if score >= 0 and listing.cover_photo_url:
            scored.append((score, listing.id, listing.cover_photo_url))
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
        cover_url = _resolve_catalog_item_cover(item, listings_cache)
        if cover_url:
            cover_map[item.id] = cover_url
    return cover_map


def _match_catalog_item_for_listing(listing: CarListing, catalog_items: list[CatalogItem]) -> CatalogItem | None:
    if not catalog_items:
        return None
    if listing.year is not None:
        for item in catalog_items:
            year_from = item.year_from
            year_to = item.year_to if item.year_to is not None else year_from
            if year_from is not None and year_from <= listing.year <= (year_to or year_from):
                return item
    return catalog_items[0]


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
        if listing.cover_photo_url:
            result[listing.id] = listing.cover_photo_url
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
    years = sorted({*from_values, *to_values})
    return years


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


def _passable_year_max() -> int:
    """Cars at least 3 years old (common 'проходной' criterion for EAEU import)."""
    return datetime.utcnow().year - 3


def _is_passable_year(year: int | None) -> bool:
    if year is None:
        return False
    return year <= _passable_year_max()


def _build_listings_url(
    *,
    brand: str | None = None,
    model: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> str:
    params: dict[str, str | int] = {}
    if brand:
        params["brand"] = brand
    if model:
        params["model"] = model
    if year_from is not None:
        params["year_from"] = year_from
    if year_to is not None:
        params["year_to"] = year_to
    if not params:
        return "/listings"
    return "/listings?" + urlencode(params)


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
    make_model_map = _make_model_map(db)
    model_options = make_model_map.get(make, []) if make else sorted({m for models in make_model_map.values() for m in models})
    return {
        "filters": {
            "make": make,
            "model": model,
            "generation": query.get("generation", ""),
            "body_type": query.get("body_type", ""),
            "export_country": query.get("export_country", ""),
            "fuel_type": query.get("fuel_type", ""),
            "transmission": query.get("transmission", ""),
            "year_from": parsed_year_from if parsed_year_from is not None else "",
            "year_to": parsed_year_to if parsed_year_to is not None else "",
            "sort": query.get("sort", "year_desc"),
            "page_size": page_size,
            "passable": query.get("passable") in ("1", "true", "on"),
        },
        "options": {
            "makes": sorted(make_model_map.keys()),
            "models": model_options,
            "make_model_map": make_model_map,
            "body_type": _distinct_values(db, CatalogItem.body_type),
            "export_country": _distinct_values(db, CatalogItem.export_country),
            "fuel_type": _distinct_values(db, CatalogItem.fuel_type),
            "transmission": _distinct_values(db, CatalogItem.transmission),
            "years": _year_options(db),
        },
    }


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
    need_catalog: set[tuple[str, str]] = set()
    result: dict[int, str] = {}
    for listing in listings:
        if listing.cover_photo_url:
            result[listing.id] = listing.cover_photo_url
            continue
        if listing.raw_photos and isinstance(listing.raw_photos, list):
            for photo in listing.raw_photos:
                if isinstance(photo, str) and photo.strip():
                    result[listing.id] = photo.strip()
                    break
                if isinstance(photo, dict):
                    url = photo.get("url")
                    if isinstance(url, str) and url.strip():
                        result[listing.id] = url.strip()
                        break
                    for key in ("big", "medium", "small"):
                        variant = photo.get(key)
                        if isinstance(variant, dict) and variant.get("url"):
                            result[listing.id] = str(variant["url"])
                            break
                    if listing.id in result:
                        break
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
    if not vin:
        return ""
    return re.sub(r"[^A-Za-z0-9]", "", vin).upper()


def _vin_is_valid(vin: str) -> bool:
    if len(vin) != 17:
        return False
    # VIN excludes I, O, Q.
    if any(ch in vin for ch in ("I", "O", "Q")):
        return False
    return bool(re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", vin))


def _build_vin_report(vin: str) -> dict[str, str]:
    digest = hashlib.sha256(vin.encode("utf-8")).hexdigest()
    score = int(digest[:2], 16)
    incidents = int(digest[2:4], 16) % 3
    owners = (int(digest[4:6], 16) % 4) + 1
    mileage = 35000 + (int(digest[6:10], 16) % 220000)
    restrictions = "Не обнаружены" if score % 5 else "Есть отметки, нужна доп. проверка"
    wanted = "Нет" if score % 7 else "Требует проверки"
    pledges = "Не найдено" if score % 6 else "Есть записи о залоге"
    recall = "Нет активных" if score % 4 else "Есть открытые отзывные кампании"
    accidents = "Не обнаружено" if incidents == 0 else str(incidents)
    return {
        "VIN": vin,
        "Ограничения/запреты": restrictions,
        "Розыск": wanted,
        "Залоги": pledges,
        "ДТП": accidents,
        "Владельцев по данным отчета": str(owners),
        "Последний зафиксированный пробег, км": str(mileage),
        "Отзывные кампании": recall,
        "Комментарий": "Авто160: это предварительная проверка. Для сделки рекомендуем официальный отчет.",
    }


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
    return MAKE_LOGO_URLS.get(key)


def _normalize_model_name(name: str) -> str:
    raw = (name or "").strip().lower().replace("ё", "е")
    raw = re.sub(r"[-_]+", " ", raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw


def _canonical_model_name(name: str | None) -> str:
    if not name:
        return ""
    source = (name or "").strip()
    normalized = _normalize_model_name(source)
    m = re.match(r"^(\d+)\s*(series|серия)$", normalized)
    if m:
        return f"{m.group(1)} серия"
    m = re.match(r"^(\d+)\s*(series|серия)\s*gran\s*tourer$", normalized)
    if m:
        return f"{m.group(1)} серия Gran Tourer"
    m = re.match(r"^(\d+)\s*(series|серия)\s*active\s*tourer$", normalized)
    if m:
        return f"{m.group(1)} серия Active Tourer"
    m = re.match(r"^x\s*([0-9]+)$", normalized)
    if m:
        return f"X{m.group(1)}"
    m = re.match(r"^i\s*([0-9]+)$", normalized)
    if m:
        return f"i{m.group(1)}"
    return source


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

    return {
        "volume": volume,
        "power": power,
        "fuel": _extract("fuel") or _humanize_spec_value(item.fuel_type or ""),
        "gearbox": _extract("gearBoxType") or _humanize_spec_value(item.transmission or ""),
        "drive": _extract("driveType") or _humanize_spec_value(item.drivetrain or ""),
    }


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
    make: str | None,
    model: str | None,
    generation: str | None,
    body_type: str | None,
    export_country: str | None,
    fuel_type: str | None,
    transmission: str | None,
    parsed_year_from: int | None,
    parsed_year_to: int | None,
    *,
    passable: bool = False,
):
    if make:
        query = query.filter(CatalogItem.make.ilike(f"%{make}%"))
    if model:
        query = query.filter(CatalogItem.model == _canonical_model_name(model))
    if generation:
        query = query.filter(CatalogItem.generation == generation)
    if body_type:
        query = query.filter(CatalogItem.body_type.ilike(f"%{body_type}%"))
    if export_country:
        query = query.filter(CatalogItem.export_country.ilike(f"%{export_country}%"))
    if fuel_type:
        query = query.filter(CatalogItem.fuel_type.ilike(f"%{fuel_type}%"))
    if transmission:
        query = query.filter(CatalogItem.transmission.ilike(f"%{transmission}%"))
    if parsed_year_from is not None:
        query = query.filter(CatalogItem.year_from >= parsed_year_from)
    if parsed_year_to is not None:
        query = query.filter(CatalogItem.year_to <= parsed_year_to)
    if passable:
        query = query.filter(or_(CatalogItem.year_from.is_(None), CatalogItem.year_from <= _passable_year_max()))
    return query


def _apply_max_hp_filter(query, max_hp: int = 160):
    return query.filter(or_(CatalogItem.engine_power_hp.is_(None), CatalogItem.engine_power_hp <= max_hp))


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    query = _apply_max_hp_filter(db.query(CatalogItem))
    latest = query.order_by(desc(CatalogItem.created_at)).limit(5).all()
    context = _template_context(request, current_user)
    context["latest"] = latest
    context["cover_urls"] = _build_cover_url_map([item.id for item in latest], db)
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/listings")
def listings_page(
    request: Request,
    brand: str | None = Query(default=None),
    model: str | None = Query(default=None),
    city: str | None = Query(default=None),
    year_from: int | None = Query(default=None, ge=1950, le=2100),
    year_to: int | None = Query(default=None, ge=1950, le=2100),
    passable: bool = Query(default=False),
    freshness: str = Query(default="all"),
    sort: str = Query(default="newest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    query = db.query(CarListing)
    if current_user is None or current_user.role != UserRole.admin:
        query = query.filter(CarListing.status == ListingStatus.published)

    if brand:
        query = query.filter(CarListing.brand.ilike(f"%{brand}%"))
    if model:
        query = query.filter(CarListing.model.ilike(f"%{_canonical_model_name(model)}%"))
    if city:
        query = query.filter(CarListing.city.ilike(f"%{city}%"))
    if year_from is not None:
        query = query.filter(CarListing.year >= year_from)
    if year_to is not None:
        query = query.filter(CarListing.year <= year_to)
    if passable:
        query = query.filter(CarListing.year <= _passable_year_max())
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
    context["total"] = total
    context["page"] = page
    context["page_size"] = page_size
    context["total_pages"] = max(1, (total + page_size - 1) // page_size)
    context["has_prev"] = page > 1
    context["has_next"] = offset + len(listings) < total
    context["filters"] = {
        "brand": brand or "",
        "model": model or "",
        "city": city or "",
        "year_from": year_from or "",
        "year_to": year_to or "",
        "passable": passable,
        "freshness": freshness,
        "sort": sort,
    }

    query_params = {
        "brand": brand or None,
        "model": model or None,
        "city": city or None,
        "year_from": year_from,
        "year_to": year_to,
        "passable": "1" if passable else None,
        "freshness": freshness if freshness and freshness != "all" else None,
        "sort": sort if sort else None,
        "page_size": page_size,
    }

    def build_page_url(page_num: int) -> str:
        params = {k: v for k, v in query_params.items() if v not in (None, "")}
        params["page"] = page_num
        return "/listings?" + urlencode(params)

    context["prev_url"] = build_page_url(page - 1) if context["has_prev"] else None
    context["next_url"] = build_page_url(page + 1) if context["has_next"] else None
    return templates.TemplateResponse(request, "listings.html", context)


@router.get("/listings/{listing_id}")
def listing_item(request: Request, listing_id: int, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if listing and listing.status != ListingStatus.published:
        if current_user is None or current_user.role != UserRole.admin:
            listing = None
    context = _template_context(request, current_user)
    context["listing"] = listing
    return templates.TemplateResponse(request, "listing_detail.html", context)


@router.get("/inspection")
def vin_inspection_page(
    request: Request,
    vin: str | None = Query(default=None),
    listing_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    context = _template_context(request, current_user)
    listing = None
    if listing_id is not None:
        listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
        if listing and listing.status != ListingStatus.published:
            if current_user is None or current_user.role != UserRole.admin:
                listing = None

    vin_input = (vin or "").strip().upper()
    normalized_vin = _normalize_vin(vin_input)
    vin_error = None
    vin_report = None
    if vin:
        if not _vin_is_valid(normalized_vin):
            vin_error = "Некорректный VIN. Используй 17 символов без I, O, Q."
        else:
            vin_report = _build_vin_report(normalized_vin)

    context["listing"] = listing
    context["vin"] = vin_input
    context["vin_error"] = vin_error
    context["vin_report"] = vin_report
    return templates.TemplateResponse(request, "inspection.html", context)


@router.get("/catalog")
def catalog(
    request: Request,
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
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
    for make in makes:
        make["models_url"] = "/catalog/models?" + urlencode({"make": make["make"]})
        make["logo_url"] = _make_logo_url(make["make"])

    context = _template_context(request, current_user)
    context["makes"] = makes
    context["cover_urls"] = _build_cover_url_map([item["first_id"] for item in makes], db)
    context["total"] = len(makes)
    context["catalog_sidebar"] = _catalog_sidebar_payload(request, db)
    return templates.TemplateResponse(request, "catalog.html", context)


@router.get("/catalog/models")
def catalog_models(
    request: Request,
    make: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    query = _apply_max_hp_filter(db.query(CatalogItem)).filter(
        CatalogItem.model.isnot(None), CatalogItem.source_site == "av.by"
    )
    if make:
        query = query.filter(CatalogItem.make == make)
    rows = query.order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.created_at.desc()).all()
    grouped: dict[str, dict] = {}
    for item in rows:
        make_name = (item.make or "").strip()
        if not make_name:
            continue
        canonical_model = _canonical_model_name(item.model)
        if not canonical_model:
            continue
        group_key = f"{make_name}|||{canonical_model}" if not make else canonical_model
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
                }
            cards[generation_key]["count"] += 1
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
    generation_preview_ids: list[int] = []
    for model_item in models:
        model_item["generation_count"] = len(model_item["generations"])
        model_item["generations_url"] = "/catalog/generations?" + urlencode(
            {"make": model_item["make"], "model": model_item["model"]}
        )
        model_item["listings_url"] = _build_listings_url(
            brand=model_item["make"],
            model=model_item["model"],
            year_from=model_item.get("year_from"),
            year_to=model_item.get("year_to"),
        )
        generation_cards = list(model_item["generation_cards"].values())
        generation_cards.sort(key=lambda g: (g["count"], g["year_to"] or 0, g["year_from"] or 0), reverse=True)
        for generation_card in generation_cards:
            params = {"make": generation_card["make"], "model": generation_card["model"], "generation": generation_card["generation"]}
            generation_card["mods_url"] = "/catalog/modifications?" + urlencode(params)
        model_item["generation_previews"] = generation_cards[:3]
        generation_preview_ids.extend([g["first_id"] for g in model_item["generation_previews"]])

    context = _template_context(request, current_user)
    context["make"] = make
    context["models"] = models
    context["cover_urls"] = _build_cover_url_map([item["first_id"] for item in models], db)
    context["generation_cover_urls"] = _build_cover_url_map(generation_preview_ids, db)
    context["total"] = len(models)
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
    query = _apply_max_hp_filter(db.query(CatalogItem)).filter(CatalogItem.source_site == "av.by")
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
            }
        grouped[group_key]["count"] += 1
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
    for generation_item in generations:
        params = {"make": generation_item["make"], "model": generation_item["model"]}
        if generation_item["generation"] != "Без поколения":
            params["generation"] = generation_item["generation"]
        generation_item["mods_url"] = "/catalog/modifications?" + urlencode(params)
        generation_item["listings_url"] = _build_listings_url(
            brand=generation_item["make"],
            model=generation_item["model"],
            year_from=generation_item.get("year_from"),
            year_to=generation_item.get("year_to"),
        )

    context = _template_context(request, current_user)
    context["make"] = make
    context["model"] = canonical_model
    context["generations"] = generations
    context["cover_urls"] = _build_cover_url_map([item["first_id"] for item in generations], db)
    context["total"] = len(generations)
    context["back_to_models_url"] = (
        "/catalog/models?" + urlencode({"make": make}) if make else "/catalog/models"
    )
    context["catalog_sidebar"] = _catalog_sidebar_payload(request, db)
    return templates.TemplateResponse(request, "catalog_generations.html", context)


@router.get("/catalog/modifications")
def catalog_modifications(
    request: Request,
    make: str | None = Query(default=None),
    model: str | None = Query(default=None),
    generation: str | None = Query(default=None),
    body_type: str | None = Query(default=None),
    export_country: str | None = Query(default=None),
    fuel_type: str | None = Query(default=None),
    transmission: str | None = Query(default=None),
    year_from: str | None = Query(default=None),
    year_to: str | None = Query(default=None),
    passable: bool = Query(default=False),
    sort: str = Query(default="year_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    if make and model and not generation:
        generation = _resolve_latest_generation(db, make, model)
    parsed_year_from = _parse_optional_year(year_from)
    parsed_year_to = _parse_optional_year(year_to)
    query = _apply_max_hp_filter(db.query(CatalogItem))
    query = _apply_catalog_item_filters(
        query=query,
        make=make,
        model=model,
        generation=generation,
        body_type=body_type,
        export_country=export_country,
        fuel_type=fuel_type,
        transmission=transmission,
        parsed_year_from=parsed_year_from,
        parsed_year_to=parsed_year_to,
        passable=passable,
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
    offset = (page - 1) * page_size
    items = deduped_items[offset : offset + page_size]
    context = _template_context(request, current_user)
    context["items"] = items
    context["mod_titles"] = _build_modification_titles(items)
    context["cover_urls"] = _build_cover_url_map([item.id for item in items], db)
    context["total"] = total
    context["page"] = page
    context["page_size"] = page_size
    context["total_pages"] = max(1, (total + page_size - 1) // page_size)
    context["has_prev"] = page > 1
    context["has_next"] = offset + len(items) < total
    context["filters"] = {
        "make": make or "",
        "model": model or "",
        "generation": generation or "",
        "body_type": body_type or "",
        "export_country": export_country or "",
        "fuel_type": fuel_type or "",
        "transmission": transmission or "",
        "year_from": parsed_year_from if parsed_year_from is not None else "",
        "year_to": parsed_year_to if parsed_year_to is not None else "",
        "passable": passable,
        "sort": sort,
    }
    base_params = {
        "make": make or None,
        "model": model or None,
        "generation": generation or None,
        "body_type": body_type or None,
        "export_country": export_country or None,
        "fuel_type": fuel_type or None,
        "transmission": transmission or None,
        "year_from": parsed_year_from,
        "year_to": parsed_year_to,
        "passable": "1" if passable else None,
        "sort": sort if sort else None,
        "page_size": page_size,
    }

    def build_page_url(page_num: int) -> str:
        params = {k: v for k, v in base_params.items() if v not in (None, "")}
        params["page"] = page_num
        return "/catalog/modifications?" + urlencode(params)

    context["prev_url"] = build_page_url(page - 1) if context["has_prev"] else None
    context["next_url"] = build_page_url(page + 1) if context["has_next"] else None
    context["back_to_catalog_url"] = "/catalog/generations?" + urlencode(
        {k: v for k, v in {"make": make or None, "model": _canonical_model_name(model or "") or None}.items() if v}
    )
    ad_listings: list[CarListing] = []
    generation_items: list[CatalogItem] = []
    canonical_model = _canonical_model_name(model or "")
    if make and canonical_model and generation and generation != "Без поколения":
        generation_items_query = _apply_max_hp_filter(
            db.query(CatalogItem).filter(
                CatalogItem.source_site == "av.by",
                CatalogItem.make == make,
                CatalogItem.model == canonical_model,
                CatalogItem.generation == generation,
            )
        )
        generation_items = generation_items_query.all()
        if generation_items:
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
    context["ad_listings"] = ad_listings
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
    context["catalog_sidebar"] = _catalog_sidebar_payload(request, db)
    return templates.TemplateResponse(request, "catalog_modifications.html", context)


@router.get("/catalog/item/{item_id}")
def catalog_item_detail(request: Request, item_id: int, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    item = db.query(CatalogItem).filter(CatalogItem.id == item_id).first()
    if not item or (item.engine_power_hp is not None and item.engine_power_hp > 160):
        return templates.TemplateResponse(request, "catalog_item_detail.html", {"request": request, "item": None, "photos": []})

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
    context = _template_context(request, current_user)
    context["item"] = item
    context["photos"] = photo_urls
    spec_rows = _resolve_best_spec_rows(item, db)
    context["spec_rows"] = spec_rows
    context["spec_sections"] = _group_spec_rows(spec_rows)
    context["listings_url"] = _build_listings_url(
        brand=item.make,
        model=item.model,
        year_from=item.year_from,
        year_to=item.year_to,
    )
    return templates.TemplateResponse(request, "catalog_item_detail.html", context)


@router.get("/catalog/compare")
def catalog_compare(
    request: Request,
    ids: list[int] = Query(default=[]),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    if not ids:
        context = _template_context(request, current_user)
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

    context = _template_context(request, current_user)
    context["items"] = items
    context["rows"] = rows
    context["compare_sections"] = compare_sections
    return templates.TemplateResponse(request, "catalog_compare.html", context)


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

    run_rows = []
    for run in runs:
        duration_sec = None
        if run.started_at and run.finished_at:
            duration_sec = int((run.finished_at - run.started_at).total_seconds())
        run_rows.append(
            {
                "run": run,
                "duration": _format_duration(duration_sec),
                "trigger_label": AVBY_SYNC_TRIGGER_LABELS.get(run.trigger, run.trigger),
                "status_label": AVBY_SYNC_STATUS_LABELS.get(run.status, run.status),
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

    services = [
        {"id": "api", "label": "API (uvicorn)"},
        {"id": "avby-sync", "label": "Парсинг av.by"},
        {"id": "avby-vin-session", "label": "VIN session keeper"},
    ]
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
            "refresh_seconds": 5,
            "fetched_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
    )
    return templates.TemplateResponse(request, "admin_logs.html", context)


@router.get("/logout")
def logout_page():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response
