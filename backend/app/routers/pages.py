from collections import defaultdict
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from jose import JWTError
from sqlalchemy import case, desc
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CarListing, CatalogItem, CatalogItemPhoto, User, UserRole
from app.security import decode_token, is_token_revoked
from app.storage import generate_download_url

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
    "frontTrackWidth": "Колея передняя",
    "fuel": "Топливо",
    "fuelTankCapacity": "Объем бака",
    "fullWeight": "Полная масса",
    "gearBoxType": "Коробка передач",
    "groundClearance": "Клиренс",
    "height": "Высота",
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
        cover_map[photo.catalog_item_id] = generate_download_url(photo.storage_key)
    return cover_map


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
        .filter(CatalogItem.make.isnot(None), CatalogItem.model.isnot(None))
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


def _resolve_latest_generation(db: Session, make: str, model: str) -> str | None:
    canonical_model = _canonical_model_name(model)
    rows = (
        db.query(CatalogItem.generation, CatalogItem.year_from)
        .filter(
            CatalogItem.make == make,
            CatalogItem.model == canonical_model,
            CatalogItem.generation.isnot(None),
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
            rows.append((_humanize_spec_key(key), display))

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
                rows.append((label, str(display)))
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
    values: dict[str, str] = {
        "Модель": f"{item.make or ''} {item.model or ''}".strip() or "—",
        "Поколение": item.generation or "—",
        "Годы выпуска": f"{item.year_from or '?'} - {item.year_to or '?'}",
        "Тип кузова": item.body_type or "—",
        "Топливо": item.fuel_type or "—",
        "Привод": item.drivetrain or "—",
        "Коробка передач": item.transmission or "—",
        "Мощность": f"{item.engine_power_hp} hp" if item.engine_power_hp else "—",
        "Объем двигателя": f"{item.engine_volume_l} л" if item.engine_volume_l else "—",
    }
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
    return query


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    query = db.query(CatalogItem)
    latest = query.order_by(desc(CatalogItem.created_at)).limit(5).all()
    context = _template_context(request, current_user)
    context["latest"] = latest
    context["cover_urls"] = _build_cover_url_map([item.id for item in latest], db)
    return templates.TemplateResponse(request, "index.html", context)


@router.get("/catalog")
def catalog(
    request: Request,
    make: str | None = Query(default=None),
    model: str | None = Query(default=None),
    generation: str | None = Query(default=None),
    body_type: str | None = Query(default=None),
    export_country: str | None = Query(default=None),
    year_from: str | None = Query(default=None),
    year_to: str | None = Query(default=None),
    sort: str = Query(default="year_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=50),
    db: Session = Depends(get_db),
):
    current_user = _resolve_user_from_request(request, db)
    query = db.query(CatalogItem)
    parsed_year_from = _parse_optional_year(year_from)
    parsed_year_to = _parse_optional_year(year_to)
    query = _apply_catalog_item_filters(
        query=query,
        make=make,
        model=model,
        generation=generation,
        body_type=body_type,
        export_country=export_country,
        fuel_type=None,
        transmission=None,
        parsed_year_from=parsed_year_from,
        parsed_year_to=parsed_year_to,
    )
    rows = query.all()

    grouped: dict[tuple, dict] = {}
    for item in rows:
        canonical_model = _canonical_model_name(item.model)
        key = (
            item.make or "",
            canonical_model or "",
        )
        if key not in grouped:
            grouped[key] = {
                "make": item.make,
                "model": canonical_model or item.model,
                "generation": item.generation,
                "year_from": item.year_from,
                "year_to": item.year_to,
                "body_type": item.body_type,
                "export_country": item.export_country,
                "min_price_rub": item.min_price_rub,
                "count": 0,
                "first_id": item.id,
                "generations": set([item.generation]) if item.generation else set(),
                "generation_count": 0,
                "generation_year_from_map": {},
            }
        grouped[key]["count"] += 1
        if item.generation:
            grouped[key]["generations"].add(item.generation)
            current_year = grouped[key]["generation_year_from_map"].get(item.generation)
            if current_year is None or (item.year_from is not None and item.year_from > current_year):
                grouped[key]["generation_year_from_map"][item.generation] = item.year_from
        grouped[key]["generation_count"] = len(grouped[key]["generations"])
        if grouped[key]["year_from"] is None or (item.year_from is not None and item.year_from < grouped[key]["year_from"]):
            grouped[key]["year_from"] = item.year_from
        if grouped[key]["year_to"] is None or (item.year_to is not None and item.year_to > grouped[key]["year_to"]):
            grouped[key]["year_to"] = item.year_to
        if item.min_price_rub is not None:
            current = grouped[key]["min_price_rub"]
            if current is None or item.min_price_rub < current:
                grouped[key]["min_price_rub"] = item.min_price_rub

    groups = list(grouped.values())
    for group in groups:
        group["generation_list"] = sorted(group["generations"])
        generation_years = group.get("generation_year_from_map", {})
        group["default_generation"] = None
        if generation_years:
            # Open the newest generation by default from the common model card.
            group["default_generation"] = max(
                generation_years.keys(), key=lambda gen: (generation_years.get(gen) or 0, gen)
            )
        if group["generation_count"] == 1 and group["generation_list"]:
            group["generation"] = group["generation_list"][0]
        elif group["generation_count"] > 1:
            group["generation"] = ", ".join(group["generation_list"][:3])
            if group["generation_count"] > 3:
                group["generation"] += "…"
        else:
            group["generation"] = None
    if sort == "year_asc":
        groups.sort(key=lambda g: (g["year_from"] or 0, g["make"] or "", g["model"] or ""))
    elif sort == "year_desc":
        groups.sort(key=lambda g: (g["year_from"] or 0, g["make"] or "", g["model"] or ""), reverse=True)
    else:
        groups.sort(key=lambda g: (g["make"] or "", g["model"] or "", g["generation"] or ""))

    total = len(groups)
    offset = (page - 1) * page_size
    paged_groups = groups[offset : offset + page_size]

    for g in paged_groups:
        params = {
            "make": g["make"],
            "model": g["model"],
            "generation": g["default_generation"] or None,
        }
        g["mods_url"] = "/catalog/modifications?" + urlencode({k: v for k, v in params.items() if v not in (None, "")})

    context = _template_context(request, current_user)
    context["groups"] = paged_groups
    context["cover_urls"] = _build_cover_url_map([item["first_id"] for item in paged_groups], db)
    context["filters"] = {
        "make": make or "",
        "model": model or "",
        "generation": generation or "",
        "body_type": body_type or "",
        "export_country": export_country or "",
        "year_from": parsed_year_from if parsed_year_from is not None else "",
        "year_to": parsed_year_to if parsed_year_to is not None else "",
        "sort": sort,
    }
    context["options"] = {
        "make": _distinct_values(db, CatalogItem.make),
        "model": _distinct_canonical_models(db),
        "generation": _distinct_values(db, CatalogItem.generation),
        "body_type": _distinct_values(db, CatalogItem.body_type),
        "export_country": _distinct_values(db, CatalogItem.export_country),
        "fuel_type": _distinct_values(db, CatalogItem.fuel_type),
        "transmission": _distinct_values(db, CatalogItem.transmission),
        "years": _year_options(db),
    }
    context["make_model_map"] = _make_model_map(db)
    context["page"] = page
    context["page_size"] = page_size
    context["total"] = total
    context["total_pages"] = max(1, (total + page_size - 1) // page_size)
    context["has_prev"] = page > 1
    context["has_next"] = offset + len(paged_groups) < total

    query_params = {
        "make": make or None,
        "model": model or None,
        "generation": generation or None,
        "body_type": body_type or None,
        "export_country": export_country or None,
        "year_from": parsed_year_from,
        "year_to": parsed_year_to,
        "sort": sort if sort else None,
        "page_size": page_size,
    }

    def build_page_url(page_num: int) -> str:
        params = {k: v for k, v in query_params.items() if v is not None and v != ""}
        params["page"] = page_num
        return "/catalog?" + urlencode(params)

    context["prev_url"] = build_page_url(page - 1) if context["has_prev"] else None
    context["next_url"] = build_page_url(page + 1) if context["has_next"] else None
    return templates.TemplateResponse(request, "catalog.html", context)


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
    query = db.query(CatalogItem)
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
    )
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
    total = query.count()
    offset = (page - 1) * page_size
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

    items = query.offset(offset).limit(page_size).all()
    context = _template_context(request, current_user)
    context["items"] = items
    context["spec_rows_by_id"] = {item.id: _resolve_best_spec_rows(item, db) for item in items}
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
        "sort": sort if sort else None,
        "page_size": page_size,
    }

    def build_page_url(page_num: int) -> str:
        params = {k: v for k, v in base_params.items() if v not in (None, "")}
        params["page"] = page_num
        return "/catalog/modifications?" + urlencode(params)

    context["prev_url"] = build_page_url(page - 1) if context["has_prev"] else None
    context["next_url"] = build_page_url(page + 1) if context["has_next"] else None
    context["back_to_catalog_url"] = "/catalog?" + urlencode(
        {
            k: v
            for k, v in {
                "make": make or None,
                "model": model or None,
                "generation": generation or None,
                "body_type": body_type or None,
                "export_country": export_country or None,
                "year_from": parsed_year_from,
                "year_to": parsed_year_to,
            }.items()
            if v not in (None, "")
        }
    )
    return templates.TemplateResponse(request, "catalog_modifications.html", context)


@router.get("/catalog/item/{item_id}")
def catalog_item_detail(request: Request, item_id: int, db: Session = Depends(get_db)):
    current_user = _resolve_user_from_request(request, db)
    item = db.query(CatalogItem).filter(CatalogItem.id == item_id).first()
    if not item:
        return templates.TemplateResponse(request, "catalog_item_detail.html", {"request": request, "item": None, "photos": []})

    photos = (
        db.query(CatalogItemPhoto)
        .filter(CatalogItemPhoto.catalog_item_id == item_id)
        .order_by(CatalogItemPhoto.is_cover.desc(), CatalogItemPhoto.sort_order.asc(), CatalogItemPhoto.id.asc())
        .all()
    )
    photo_urls = [generate_download_url(photo.storage_key) for photo in photos]
    context = _template_context(request, current_user)
    context["item"] = item
    context["photos"] = photo_urls
    spec_rows = _resolve_best_spec_rows(item, db)
    context["spec_rows"] = spec_rows
    context["spec_sections"] = _group_spec_rows(spec_rows)
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
    items = [by_id[item_id] for item_id in unique_ids if item_id in by_id]

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
    current_user = _resolve_user_from_request(request, db)
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if listing and listing.status != ListingStatus.published:
        if current_user is None or current_user.role != UserRole.admin:
            listing = None
    context = _template_context(request, current_user)
    context["listing"] = listing
    return templates.TemplateResponse(request, "listing_detail.html", context)


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
            "file_url": generate_download_url(p.storage_key),
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


@router.get("/logout")
def logout_page():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response
