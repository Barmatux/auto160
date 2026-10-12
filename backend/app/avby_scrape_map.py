"""Map scrape-platform ``listings`` rows (source=avby) into Auto160 listing payloads."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.autoplius_map import absolute_media_url, extract_storage_key

DEFAULT_MAX_HP = 160
DEFAULT_YEAR_MIN = 2010
DEFAULT_PRICE_USD_MIN = 10_000


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^\d-]", "", str(value))
    if not cleaned or cleaned == "-":
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


def parse_avby_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed


@dataclass
class AvbyScrapeMappedListing:
    avby_id: int
    external_id: str
    source_url: str | None
    title: str
    brand: str | None
    model: str | None
    generation: str | None
    year: int | None
    mileage: int | None
    price_byn: Decimal | None
    price_byn_missing: bool
    city: str | None
    body_type: str | None
    drive_type: str | None
    engine_type: str | None
    transmission_type: str | None
    engine_capacity_l: float | None
    engine_power_hp: int | None
    cover_photo_url: str | None
    photo_urls: list[str] = field(default_factory=list)
    source_photo_urls: list[str] = field(default_factory=list)
    description: str | None = None
    seller_name: str | None = None
    organization_id: int | None = None
    vin_indicated: bool = False
    avby_published_at: datetime | None = None
    avby_renewed_at: datetime | None = None
    detail_scraped: bool = False
    skip_reason: str | None = None


def _photo_urls_from_row(row: dict[str, Any], *, use_app_proxy: bool = True) -> tuple[str | None, list[str], list[str]]:
    """Return (cover, media_urls, source_http_urls)."""
    params = row.get("parameters") if isinstance(row.get("parameters"), dict) else {}
    source_urls: list[str] = []
    for raw in params.get("source_photo_urls") or []:
        if isinstance(raw, str) and raw.strip().startswith("http"):
            source_urls.append(raw.strip())

    media_urls: list[str] = []
    for raw in row.get("photo_urls") or []:
        if not isinstance(raw, str) or not raw.strip():
            continue
        text = raw.strip()
        key = extract_storage_key(text)
        if key and key.startswith("avby/"):
            media = absolute_media_url(key, use_app_proxy=use_app_proxy)
            if media and media not in media_urls:
                media_urls.append(media)
        elif text.startswith("/media/object?key=") or text.startswith("/media/autoplius?key="):
            if text not in media_urls:
                media_urls.append(text)
        elif text.startswith("http") and text not in source_urls:
            source_urls.append(text)

    cover_raw = row.get("photo_url")
    cover: str | None = None
    if isinstance(cover_raw, str) and cover_raw.strip():
        text = cover_raw.strip()
        key = extract_storage_key(text)
        if key and key.startswith("avby/"):
            cover = absolute_media_url(key, use_app_proxy=use_app_proxy)
        elif text.startswith("/media/object?key=") or text.startswith("/media/autoplius?key="):
            cover = text
        elif text.startswith("http"):
            if text not in source_urls:
                source_urls.insert(0, text)
    if cover is None and media_urls:
        cover = media_urls[0]
    return cover, media_urls, source_urls


def map_avby_scrape_row(
    row: dict[str, Any],
    *,
    max_hp: int = DEFAULT_MAX_HP,
    year_min: int = DEFAULT_YEAR_MIN,
    price_usd_min: int = DEFAULT_PRICE_USD_MIN,
    require_detail: bool = True,
    use_app_proxy: bool = True,
) -> AvbyScrapeMappedListing:
    external_id = str(row.get("external_id") or "").strip()
    avby_id = _to_int(external_id)
    params = row.get("parameters") if isinstance(row.get("parameters"), dict) else {}
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}

    brand = str(params.get("make") or params.get("brand") or "").strip() or None
    model = str(params.get("model") or "").strip() or None
    generation = str(params.get("generation") or "").strip() or None
    year = _to_int(row.get("year"))
    mileage = _to_int(row.get("mileage_km")) or 0
    hp = _to_int(params.get("engine_power_hp") or row.get("engine"))
    if hp is None and isinstance(row.get("engine"), str):
        hp = _to_int(row.get("engine"))
    engine_l = _to_float(row.get("engine_liters") or params.get("engine_capacity"))
    price_byn = _to_float(params.get("price_byn"))
    price_usd = _to_float(params.get("price_usd"))
    city = (row.get("city") or "").strip() or None
    body_type = (row.get("body_type") or "").strip() or None
    drive_type = str(params.get("drive") or params.get("drive_type") or "").strip() or None
    engine_type = (row.get("fuel") or "").strip() or None
    transmission_type = (row.get("transmission") or "").strip() or None
    source_url = (row.get("url") or "").strip() or None
    title = (row.get("title") or "").strip()
    description = (row.get("description_ru") or row.get("description") or "").strip() or None
    seller_name = str(params.get("seller_name") or "").strip() or None
    organization_id = _to_int(params.get("organization_id"))
    vin_indicated = bool(params.get("vin_indicated") or row.get("has_vin_badge"))
    published = parse_avby_datetime(params.get("published_at") or raw.get("publishedAt"))
    renewed = parse_avby_datetime(params.get("renewed_at") or raw.get("renewedAt"))

    cover, media_urls, source_urls = _photo_urls_from_row(row, use_app_proxy=use_app_proxy)

    skip_reason: str | None = None
    if not external_id or avby_id is None:
        skip_reason = "missing_external_id"
    elif require_detail and not row.get("detail_scraped"):
        skip_reason = "detail_not_scraped"
    elif not brand or not model:
        skip_reason = "missing_brand_model"
    elif year is None:
        skip_reason = "missing_year"
    elif year < year_min:
        skip_reason = "year_below_min"
    elif price_usd is not None and price_usd < price_usd_min:
        skip_reason = "price_usd_below_min"
    elif hp is None:
        skip_reason = "missing_hp"
    elif hp > max_hp:
        skip_reason = "hp_above_max"

    if not title and brand and model and year:
        title = f"{brand} {model} {year}"
    if not title:
        title = f"av.by #{avby_id or external_id}"

    desc_body = description or ""
    description_out = (
        f"{desc_body}\n\n"
        f"Источник: av.by\n"
        f"URL: {source_url or ''}\n"
        f"AVBY_ID: {avby_id or external_id}"
    ).strip()

    price_dec = Decimal(str(price_byn)) if price_byn is not None else None
    return AvbyScrapeMappedListing(
        avby_id=avby_id or 0,
        external_id=external_id,
        source_url=source_url,
        title=title[:180],
        brand=(brand or "")[:80] or None,
        model=(model or "")[:80] or None,
        generation=(generation or "")[:120] or None,
        year=year,
        mileage=mileage,
        price_byn=price_dec,
        price_byn_missing=price_byn is None,
        city=(city or "Не указан")[:80],
        body_type=(body_type or "")[:60] or None,
        drive_type=(drive_type or "")[:40] or None,
        engine_type=(engine_type or "")[:40] or None,
        transmission_type=(transmission_type or "")[:40] or None,
        engine_capacity_l=engine_l,
        engine_power_hp=hp,
        cover_photo_url=cover,
        photo_urls=media_urls,
        source_photo_urls=source_urls,
        description=description_out,
        seller_name=(seller_name or "")[:120] or None,
        organization_id=organization_id,
        vin_indicated=vin_indicated,
        avby_published_at=published,
        avby_renewed_at=renewed,
        detail_scraped=bool(row.get("detail_scraped")),
        skip_reason=skip_reason,
    )
