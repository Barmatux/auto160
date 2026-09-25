"""Map Auto24 (auto24.ee) scrape DB rows into Auto160 listing payloads (no writes)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

from app.autoplius_map import (
    DEFAULT_MAX_AGE_YEARS,
    DEFAULT_MAX_ENGINE_L,
    DEFAULT_MEDIA_BUCKET,
    DEFAULT_MEDIA_ENDPOINT,
    EurRate,
    absolute_media_url,
    extract_storage_key,
    fetch_eur_rate,
    min_year_for_max_age,
    parse_year,
)

# Re-export shared helpers for importers / UI.
__all__ = [
    "DEFAULT_MAX_AGE_YEARS",
    "DEFAULT_MAX_ENGINE_L",
    "Auto24MappedListing",
    "fetch_eur_rate",
    "map_auto24_row",
    "min_year_for_max_age",
    "parse_engine_field",
]

KW_TO_HP = 1.35962

# "1.5 71kW", "2.0 173kW" — liters then kW (no unit on liters).
_ENGINE_L_KW_RE = re.compile(
    r"(?P<liters>\d+(?:[.,]\d+)?)\s+(?P<kw>\d+)\s*k\s*w\b",
    re.IGNORECASE,
)
# Bare "71kW" / "110 kW" (EVs etc.) — no liters.
_ENGINE_KW_ONLY_RE = re.compile(r"(?<![\d.,])(?P<kw>\d+)\s*k\s*w\b", re.IGNORECASE)

FUEL_MAP = {
    "bensiin": "Бензин",
    "bensiini": "Бензин",
    "diisel": "Дизель",
    "diisli": "Дизель",
    "hübriid": "Гибрид",
    "hybriid": "Гибрид",
    "hybrid": "Гибрид",
    "plugin-hybrid": "Гибрид",
    "elekter": "Электро",
    "elektriline": "Электро",
    "electric": "Электро",
    "cng": "Газ-бензин",
    "lpg": "Газ-бензин",
    "gaas": "Газ-бензин",
}

TRANSMISSION_MAP = {
    "manuaal": "Механика",
    "manual": "Механика",
    "automaat": "Автоматическая",
    "automatic": "Автоматическая",
    "cvt": "Вариатор",
    "dsg": "Робот",
    "robot": "Робот",
}

BODY_MAP = {
    "sedaan": "Седан",
    "sedan": "Седан",
    "universaal": "Универсал",
    "luukpära": "Хэтчбек 5 дв.",
    "luukpara": "Хэтчбек 5 дв.",
    "hatchback": "Хэтчбек 5 дв.",
    "mahtuniversaal": "Минивэн",
    "minivan": "Минивэн",
    "maastur": "Внедорожник 5 дв.",
    "suv": "Внедорожник 5 дв.",
    "krossover": "Кроссовер",
    "crossover": "Кроссовер",
    "kupee": "Купе",
    "coupe": "Купе",
    "kabriolett": "Кабриолет",
    "cabrio": "Кабриолет",
    "pickup": "Пикап",
    "furgoon": "Легковой фургон",
    "kaubik": "Легковой фургон",
}


@dataclass
class Auto24MappedListing:
    external_id: str
    source_url: str | None
    title: str
    brand: str | None
    model: str | None
    year: int | None
    mileage: int | None
    price_eur: int | None
    price_byn: Decimal | None
    city: str | None
    body_type: str | None
    engine_type: str | None
    transmission_type: str | None
    engine_capacity_l: float | None
    engine_power_hp: int | None
    cover_photo_url: str | None
    photo_urls: list[str] = field(default_factory=list)
    photo_storage_keys: list[str] = field(default_factory=list)
    media_bucket: str = DEFAULT_MEDIA_BUCKET
    description: str | None = None
    phone: str | None = None
    vin_masked: str | None = None
    detail_scraped: bool = False
    skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.price_byn is not None:
            payload["price_byn"] = str(self.price_byn)
        return payload


def _param_maps(row: dict[str, Any]) -> list[dict[str, Any]]:
    maps: list[dict[str, Any]] = []
    raw = row.get("raw")
    if isinstance(raw, dict):
        raw_params = raw.get("parameters")
        if isinstance(raw_params, dict):
            maps.append(raw_params)
        maps.append(raw)
    params = row.get("parameters")
    if isinstance(params, dict):
        maps.append(params)
    return maps


def _normalize_lookup(value: str | None, table: dict[str, str]) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    key = trimmed.lower().replace("ü", "u").replace("ä", "a").replace("ö", "o").replace("õ", "o")
    key = " ".join(key.split())
    mapped = table.get(key)
    if mapped:
        return mapped
    return trimmed[0].upper() + trimmed[1:]


def parse_engine_field(*texts: str | None) -> tuple[float | None, int | None]:
    """Return (engine_liters, engine_power_hp) from Auto24 engine/title strings."""
    for text in texts:
        if not text:
            continue
        cleaned = str(text).strip()
        if not cleaned:
            continue
        match = _ENGINE_L_KW_RE.search(cleaned)
        if match:
            liters = float(match.group("liters").replace(",", "."))
            kw = int(match.group("kw"))
            hp = int(round(kw * KW_TO_HP))
            if 0.5 <= liters <= 10 and 1 <= hp <= 2000:
                return liters, hp
            if 1 <= hp <= 2000:
                return None, hp
        match = _ENGINE_KW_ONLY_RE.search(cleaned)
        if match:
            kw = int(match.group("kw"))
            hp = int(round(kw * KW_TO_HP))
            if 1 <= hp <= 2000:
                return None, hp
    return None, None


def _brand_model(row: dict[str, Any]) -> tuple[str | None, str | None]:
    for params in _param_maps(row):
        make = (params.get("make") or params.get("brand") or "").strip()
        model = (params.get("model") or "").strip()
        if make and model:
            return make, model
        if make:
            return make, model or None
    title = (row.get("title") or "").strip()
    if not title:
        return None, None
    # Titles like "Volvo V90 Cross Country 2.0 173kW"
    head = re.split(r"\s+\d+(?:[.,]\d+)?\s+\d+\s*k\s*w\b", title, maxsplit=1, flags=re.I)[0].strip()
    parts = head.split(None, 1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


_COUNTRY_CITY_ALIASES = frozenset(
    {
        "эстония",
        "estonia",
        "eesti",
        "est",
        "ee",
    }
)

_CITY_PARAM_KEYS = (
    "city",
    "city_raw",
    "city_name",
    "location",
    "location_name",
    "seller_location",
    "seller_city",
    "asukoht",
    "Asukoht",
    "address_city",
    "settlement",
    "parish",
    "vald",
)


def _looks_like_country_only(value: str) -> bool:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        return True
    return cleaned.casefold() in _COUNTRY_CITY_ALIASES


def _city_candidate(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in _CITY_PARAM_KEYS:
            nested = _city_candidate(value.get(key))
            if nested:
                return nested
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            nested = _city_candidate(item)
            if nested:
                return nested
        return None
    text = str(value).strip()
    if not text or _looks_like_country_only(text):
        return None
    # "Tallinn, Harjumaa" / "Harjumaa / Tallinn" — keep first meaningful chunk.
    for sep in (",", "/", "|", "·"):
        if sep in text:
            parts = [part.strip() for part in text.split(sep) if part.strip()]
            for part in parts:
                if not _looks_like_country_only(part):
                    return part[:80]
            return None
    return text[:80]


def _city(row: dict[str, Any]) -> str | None:
    """Seller city from scrape column or detail parameters (location / Asukoht)."""
    direct = _city_candidate(row.get("city"))
    if direct:
        return direct
    for params in _param_maps(row):
        for key in _CITY_PARAM_KEYS:
            candidate = _city_candidate(params.get(key))
            if candidate:
                return candidate
        # Case-insensitive key scan for Estonian/English labels.
        for key, value in params.items():
            if not isinstance(key, str):
                continue
            key_cf = key.casefold().replace("ü", "u").replace("ä", "a").replace("ö", "o")
            if key_cf in {
                "city",
                "location",
                "asukoht",
                "seller_location",
                "seller_city",
                "location_name",
                "city_name",
                "city_raw",
            }:
                candidate = _city_candidate(value)
                if candidate:
                    return candidate
        # Spec tables sometimes store [{"name": "Asukoht", "value": "Tallinn"}, ...]
        for list_key in ("specs", "details", "attributes", "fields", "items"):
            items = params.get(list_key)
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("name") or item.get("label") or item.get("key") or "")
                label_cf = label.casefold().replace("ü", "u")
                if label_cf in {"asukoht", "location", "city", "seller location"}:
                    candidate = _city_candidate(item.get("value") or item.get("text"))
                    if candidate:
                        return candidate
    return None


def _cdn_photo_urls(row: dict[str, Any]) -> list[str]:
    """Original Auto24 CDN URLs from parameters (fallback when S3 keys are missing)."""
    urls: list[str] = []
    for params in _param_maps(row):
        raw_list = params.get("source_photo_urls")
        if not isinstance(raw_list, list):
            continue
        for item in raw_list:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if cleaned.startswith("http://") or cleaned.startswith("https://"):
                if cleaned not in urls:
                    urls.append(cleaned)
        if urls:
            break
    return urls


def map_auto24_row(
    row: dict[str, Any],
    *,
    eur_rate: EurRate | None,
    media_base: str | None = None,
    media_bucket: str = DEFAULT_MEDIA_BUCKET,
    media_endpoint: str = DEFAULT_MEDIA_ENDPOINT,
    use_app_proxy: bool = True,
    max_hp: int | None = 160,
    max_age_years: int | None = DEFAULT_MAX_AGE_YEARS,
    max_engine_l: float | None = DEFAULT_MAX_ENGINE_L,
    require_detail: bool = True,
) -> Auto24MappedListing:
    external_id = str(row.get("external_id") or "").strip()
    title = (row.get("title") or "").strip()
    brand, model = _brand_model(row)
    year = parse_year(row.get("year"))
    price_eur = row.get("price_eur")
    try:
        price_eur_i = int(price_eur) if price_eur is not None else None
    except (TypeError, ValueError):
        price_eur_i = None
    price_byn = eur_rate.eur_to_byn(price_eur_i) if eur_rate and price_eur_i is not None else None

    engine_text = (row.get("engine") or "").strip() or None
    if not engine_text:
        raw = row.get("raw")
        if isinstance(raw, dict):
            engine_text = (raw.get("engine") or "").strip() or None
    engine_l, hp = parse_engine_field(engine_text, title)
    if engine_l is None and row.get("engine_liters") is not None:
        try:
            engine_l = float(row["engine_liters"])
        except (TypeError, ValueError):
            engine_l = None

    # Prefer uploaded S3 keys from scrape-platform; CDN only if keys are absent.
    photo_urls_raw = row.get("photo_urls") or []
    if not isinstance(photo_urls_raw, list):
        photo_urls_raw = []
    photo_keys = [k for k in (extract_storage_key(p) for p in photo_urls_raw) if k]
    cover_key = extract_storage_key(row.get("photo_url"))
    if cover_key and cover_key not in photo_keys:
        photo_keys = [cover_key, *photo_keys]

    if photo_keys:
        photo_urls = [
            u
            for u in (
                absolute_media_url(
                    key,
                    media_base=media_base,
                    media_bucket=media_bucket,
                    media_endpoint=media_endpoint,
                    use_app_proxy=use_app_proxy,
                )
                for key in photo_keys
            )
            if u
        ]
        cover = (
            absolute_media_url(
                cover_key or (photo_keys[0] if photo_keys else None),
                media_base=media_base,
                media_bucket=media_bucket,
                media_endpoint=media_endpoint,
                use_app_proxy=use_app_proxy,
            )
            or (photo_urls[0] if photo_urls else None)
        )
    else:
        cdn_urls = _cdn_photo_urls(row)
        photo_urls = cdn_urls
        cover = cdn_urls[0] if cdn_urls else None

    body_type = _normalize_lookup(row.get("body_type"), BODY_MAP)
    engine_type = _normalize_lookup(row.get("fuel"), FUEL_MAP)
    transmission_type = _normalize_lookup(row.get("transmission"), TRANSMISSION_MAP)

    skip: str | None = None
    if not external_id:
        skip = "missing_external_id"
    elif require_detail and not row.get("detail_scraped"):
        skip = "detail_not_scraped"
    elif not brand or not model:
        skip = "brand_model_parse_failed"
    elif year is None:
        skip = "year_parse_failed"
    elif price_eur_i is None or price_eur_i <= 0:
        skip = "missing_price_eur"
    elif max_hp is not None and hp is None:
        skip = "hp_missing"
    elif max_hp is not None and hp is not None and hp > max_hp:
        skip = f"hp_over_{max_hp}"
    elif max_age_years is not None and year < min_year_for_max_age(max_age_years):
        skip = f"age_over_{max_age_years}"
    elif max_engine_l is not None and engine_l is None:
        skip = "engine_l_missing"
    elif max_engine_l is not None and engine_l is not None and engine_l > max_engine_l:
        skip = f"engine_l_over_{max_engine_l}"

    description = (row.get("description_ru") or row.get("description") or "").strip() or None

    return Auto24MappedListing(
        external_id=external_id,
        source_url=(row.get("url") or None),
        title=title[:180],
        brand=brand,
        model=model,
        year=year,
        mileage=int(row["mileage_km"]) if row.get("mileage_km") is not None else None,
        price_eur=price_eur_i,
        price_byn=price_byn,
        city=_city(row),
        body_type=body_type,
        engine_type=engine_type,
        transmission_type=transmission_type,
        engine_capacity_l=engine_l,
        engine_power_hp=hp,
        cover_photo_url=cover,
        photo_urls=photo_urls,
        photo_storage_keys=photo_keys,
        media_bucket=media_bucket,
        description=description,
        phone=(row.get("phone") or None),
        vin_masked=(row.get("vin_masked") or None),
        detail_scraped=bool(row.get("detail_scraped")),
        skip_reason=skip,
    )
