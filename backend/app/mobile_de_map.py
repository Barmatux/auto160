"""Map mobile.de scrape DB rows into Auto160 listing payloads (no writes)."""

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

__all__ = [
    "DEFAULT_MAX_AGE_YEARS",
    "DEFAULT_MAX_ENGINE_L",
    "MobileDeMappedListing",
    "fetch_eur_rate",
    "map_mobile_de_row",
    "min_year_for_max_age",
    "parse_engine_field",
]

KW_TO_HP = 1.35962

# "1.499 cm³, 103 kW (140 PS)" — German thousands in cm³, PS preferred for hp.
_ENGINE_CM3_RE = re.compile(r"(?P<cm3>\d{1,2}\.\d{3}|\d{3,5})\s*cm\s*[³3]", re.IGNORECASE)
_ENGINE_PS_RE = re.compile(r"(?P<ps>\d+)\s*PS\b", re.IGNORECASE)
_ENGINE_KW_RE = re.compile(r"(?P<kw>\d+)\s*k\s*w\b", re.IGNORECASE)

_TITLE_TAIL_RE = re.compile(r"\s*\|\s*mobile\.de\s*$", re.IGNORECASE)
_IN_CITY_RE = re.compile(r"\s+in\s+.+$", re.IGNORECASE)
_PLZ_PREFIX_RE = re.compile(r"^\d{4,5}\s+")

FUEL_MAP = {
    "benzin": "Бензин",
    "diesel": "Дизель",
    "hybrid (benzin/elektro)": "Гибрид",
    "hybrid (diesel/elektro)": "Гибрид",
    "hybrid": "Гибрид",
    "plugin-hybrid": "Гибрид",
    "plug-in-hybrid": "Гибрид",
    "elektro": "Электро",
    "electric": "Электро",
    "erdgas": "Газ-бензин",
    "autogas (lpg)": "Газ-бензин",
    "lpg": "Газ-бензин",
    "cng": "Газ-бензин",
    "wasserstoff": "Электро",
    "andere": "Другое",
}

TRANSMISSION_MAP = {
    "schaltgetriebe": "Механика",
    "automatik": "Автоматическая",
    "halbautomatik": "Робот",
}

BODY_MAP = {
    "limousine": "Седан",
    "kombi": "Универсал",
    "kleinwagen": "Хэтчбек 5 дв.",
    "van/minibus": "Минивэн",
    "suv/geländewagen/pickup": "Внедорожник 5 дв.",
    "suv/gelandewagen/pickup": "Внедорожник 5 дв.",
    "cabrio/roadster": "Кабриолет",
    "sportwagen/coupé": "Купе",
    "sportwagen/coupe": "Купе",
    "andere": "Другое",
}


@dataclass
class MobileDeMappedListing:
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
    # mobile.de often appends condition: "Limousine, Vorführfahrzeug"
    primary = trimmed.split(",", 1)[0].strip()
    key = primary.lower().replace("ü", "u").replace("ä", "a").replace("ö", "o")
    key = " ".join(key.split())
    mapped = table.get(key)
    if mapped:
        return mapped
    return primary[0].upper() + primary[1:]


def _parse_cm3_to_liters(raw: str) -> float | None:
    text = raw.strip()
    # German thousands: "1.499" → 1499 cm³
    if re.fullmatch(r"\d{1,2}\.\d{3}", text):
        cm3 = int(text.replace(".", ""))
    else:
        try:
            cm3 = int(float(text.replace(",", ".")))
        except ValueError:
            return None
    if cm3 < 200 or cm3 > 20000:
        return None
    return round(cm3 / 1000.0, 3)


def parse_engine_field(*texts: str | None) -> tuple[float | None, int | None]:
    """Return (engine_liters, engine_power_hp) from mobile.de engine/power strings."""
    liters: float | None = None
    hp: int | None = None
    for text in texts:
        if not text:
            continue
        cleaned = str(text).strip()
        if not cleaned:
            continue
        if liters is None:
            match = _ENGINE_CM3_RE.search(cleaned)
            if match:
                liters = _parse_cm3_to_liters(match.group("cm3"))
        if hp is None:
            ps_match = _ENGINE_PS_RE.search(cleaned)
            if ps_match:
                ps = int(ps_match.group("ps"))
                if 1 <= ps <= 2000:
                    hp = ps
            else:
                kw_match = _ENGINE_KW_RE.search(cleaned)
                if kw_match:
                    kw = int(kw_match.group("kw"))
                    candidate = int(round(kw * KW_TO_HP))
                    if 1 <= candidate <= 2000:
                        hp = candidate
        if liters is not None and hp is not None:
            break
    return liters, hp


def _clean_model_text(text: str, brand: str | None = None) -> str | None:
    cleaned = _TITLE_TAIL_RE.sub("", text).strip()
    cleaned = _IN_CITY_RE.sub("", cleaned).strip()
    if brand and cleaned.lower().startswith(brand.lower() + " "):
        cleaned = cleaned[len(brand) :].strip()
    return cleaned or None


def _brand_model(row: dict[str, Any]) -> tuple[str | None, str | None]:
    for params in _param_maps(row):
        make = (params.get("make") or params.get("brand") or "").strip()
        model_raw = (params.get("model") or "").strip()
        if make:
            model = _clean_model_text(model_raw, make) if model_raw else None
            if model:
                return make, model
            return make, None
    title = (row.get("title") or "").strip()
    if not title:
        return None, None
    cleaned = _clean_model_text(title)
    if not cleaned:
        return None, None
    parts = cleaned.split(None, 1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


def _city(row: dict[str, Any]) -> str | None:
    raw = (row.get("city") or "").strip()
    if not raw:
        for params in _param_maps(row):
            candidate = (params.get("city_raw") or "").strip()
            if candidate:
                raw = candidate
                break
    if not raw:
        return None
    return _PLZ_PREFIX_RE.sub("", raw).strip() or raw


def map_mobile_de_row(
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
) -> MobileDeMappedListing:
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
    power_texts: list[str | None] = [engine_text, title]
    for params in _param_maps(row):
        power_texts.append((params.get("power") or "").strip() or None)
        power_texts.append((params.get("displacement") or "").strip() or None)
    engine_l, hp = parse_engine_field(*power_texts)
    if engine_l is None and row.get("engine_liters") is not None:
        try:
            engine_l = float(row["engine_liters"])
        except (TypeError, ValueError):
            engine_l = None

    photo_urls_raw = row.get("photo_urls") or []
    if not isinstance(photo_urls_raw, list):
        photo_urls_raw = []
    photo_keys = [k for k in (extract_storage_key(p) for p in photo_urls_raw) if k]
    cover_key = extract_storage_key(row.get("photo_url"))
    if cover_key and cover_key not in photo_keys:
        photo_keys = [cover_key, *photo_keys]

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

    body_type = _normalize_lookup(row.get("body_type"), BODY_MAP)
    engine_type = _normalize_lookup(row.get("fuel"), FUEL_MAP)
    transmission_type = _normalize_lookup(row.get("transmission"), TRANSMISSION_MAP)

    display_title = _TITLE_TAIL_RE.sub("", title).strip() or title
    display_title = _IN_CITY_RE.sub("", display_title).strip() or display_title

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

    return MobileDeMappedListing(
        external_id=external_id,
        source_url=(row.get("url") or None),
        title=display_title[:180],
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
