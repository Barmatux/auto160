"""Map Autoplius scrape DB rows into Auto160 listing payloads (no writes)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

NBRB_EUR_URL = "https://api.nbrb.by/exrates/rates/EUR?parammode=2"

# Photos live in Yandex Object Storage (private bucket), not the scrape /media proxy.
DEFAULT_MEDIA_BUCKET = "autoplius-media"
DEFAULT_MEDIA_ENDPOINT = "https://storage.yandexcloud.net"

# Lithuania feed policy: cars up to 10 years with modest engines (in addition to ≤160 hp).
DEFAULT_MAX_AGE_YEARS = 10
DEFAULT_MAX_ENGINE_L = 1.9


def min_year_for_max_age(max_age_years: int, *, as_of: date | None = None) -> int:
    """Oldest manufacture year allowed for age ≤ max_age_years (calendar year)."""
    current = (as_of or datetime.now(timezone.utc).date()).year
    return current - int(max_age_years)

# Titles look like: "BMW 520, 2.0 l., Универсал 2019-12 m.,  | A32155778"
_TITLE_SPLIT_RE = re.compile(r"\s*,\s*")
_YEAR_RE = re.compile(r"(19|20)\d{2}")
_HP_RE = re.compile(r"(\d+)\s*\u041b\.?\s*\u0421", re.IGNORECASE)
_HP_LATIN_RE = re.compile(r"(\d+)\s*(?:HP|hp|PS|ps)\b")
_ENGINE_KEY = "\u0414\u0432\u0438\u0433\u0430\u0442\u0435\u043b\u044c"  # Двигатель

MULTI_WORD_BRANDS = (
    "Mercedes-Benz",
    "Land Rover",
    "Alfa Romeo",
    "Aston Martin",
    "Rolls-Royce",
    "Range Rover",
    "Great Wall",
    "DS Automobiles",
)


@dataclass(frozen=True)
class EurRate:
    rate: float
    scale: int
    rate_date: date

    def eur_to_byn(self, amount_eur: float | int | Decimal) -> Decimal:
        value = float(amount_eur) * self.rate / max(self.scale, 1)
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class AutopliusMappedListing:
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


def fetch_eur_rate() -> EurRate | None:
    try:
        request = Request(NBRB_EUR_URL, headers={"Accept": "application/json", "User-Agent": "Auto160/1.0"})
        with urlopen(request, timeout=10) as response:
            payload = json.load(response)
        return EurRate(
            rate=float(payload["Cur_OfficialRate"]),
            scale=int(payload.get("Cur_Scale") or 1),
            rate_date=_parse_rate_date(payload.get("Date")),
        )
    except (URLError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None


def _parse_rate_date(raw: str | None) -> date:
    if not raw:
        return datetime.now(timezone.utc).date()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return datetime.now(timezone.utc).date()


def parse_year(value: Any) -> int | None:
    if value is None:
        return None
    match = _YEAR_RE.search(str(value))
    if not match:
        return None
    year = int(match.group(0))
    if 1950 <= year <= 2100:
        return year
    return None


def parse_brand_model(title: str | None) -> tuple[str | None, str | None]:
    text = (title or "").strip()
    if not text:
        return None, None
    head = _TITLE_SPLIT_RE.split(text, maxsplit=1)[0].strip()
    # Drop trailing " | A123" junk if somehow present before comma.
    head = re.sub(r"\s*\|\s*A?\d+\s*$", "", head).strip()
    if not head:
        return None, None
    for brand in MULTI_WORD_BRANDS:
        if head.lower().startswith(brand.lower() + " "):
            model = head[len(brand) :].strip(" -")
            return brand, model or None
        if head.lower() == brand.lower():
            return brand, None
    parts = head.split(None, 1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


def _param_maps(row: dict[str, Any]) -> list[dict[str, Any]]:
    maps: list[dict[str, Any]] = []
    raw = row.get("raw")
    if isinstance(raw, dict):
        raw_params = raw.get("parameters")
        if isinstance(raw_params, dict):
            maps.append(raw_params)
    params = row.get("parameters")
    if isinstance(params, dict):
        maps.append(params)
    return maps


def extract_engine_power_hp(row: dict[str, Any]) -> int | None:
    for params in _param_maps(row):
        engine = params.get(_ENGINE_KEY)
        if not engine:
            # Fallback: any key containing "двигател"
            for key, value in params.items():
                if isinstance(key, str) and "\u0432\u0438\u0433\u0430\u0442" in key.lower() and value:
                    engine = value
                    break
        if not engine:
            continue
        text = str(engine)
        match = _HP_RE.search(text) or _HP_LATIN_RE.search(text)
        if match:
            hp = int(match.group(1))
            if 1 <= hp <= 2000:
                return hp
    return None


def extract_storage_key(path: str | None) -> str | None:
    """Normalize scrape media paths to an object key inside autoplius-media."""
    if not path:
        return None
    text = str(path).strip()
    if not text:
        return None
    if text.startswith("s3://"):
        # s3://autoplius-media/listings/...
        without = text[5:]
        if "/" not in without:
            return None
        _bucket, key = without.split("/", 1)
        return unquote(key).lstrip("/") or None
    if "media/object" in text or "key=" in text:
        parsed = urlparse(text if "://" in text else f"http://local{text if text.startswith('/') else '/' + text}")
        qs = parse_qs(parsed.query)
        if qs.get("key"):
            return unquote(qs["key"][0]).lstrip("/") or None
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        # https://storage.yandexcloud.net/autoplius-media/listings/...
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {DEFAULT_MEDIA_BUCKET, "autoplius-media"}:
            return "/".join(parts[1:])
        return parsed.path.lstrip("/") or None
    return text.lstrip("/")


def absolute_media_url(
    path: str | None,
    *,
    media_base: str | None = None,
    media_bucket: str = DEFAULT_MEDIA_BUCKET,
    media_endpoint: str = DEFAULT_MEDIA_ENDPOINT,
    use_app_proxy: bool = True,
) -> str | None:
    """Build a fetchable URL for a photo.

    Default: app proxy ``/media/autoplius?key=...`` (private Yandex bucket).
    If ``media_base`` is set, keep legacy scrape HTTP proxy mode.
    If ``use_app_proxy`` is False, build a direct Yandex path-style URL.
    """
    from urllib.parse import quote

    if media_base:
        if not path:
            return None
        text = str(path).strip()
        if not text:
            return None
        if text.startswith("http://") or text.startswith("https://"):
            return text
        base = media_base.rstrip("/")
        if not text.startswith("/"):
            text = "/" + text
        return base + text

    key = extract_storage_key(path)
    if not key:
        return None
    if use_app_proxy:
        return f"/media/autoplius?key={quote(key, safe='')}"
    endpoint = media_endpoint.rstrip("/")
    bucket = (media_bucket or DEFAULT_MEDIA_BUCKET).strip()
    return f"{endpoint}/{bucket}/{key}"


def map_autoplius_row(
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
) -> AutopliusMappedListing:
    external_id = str(row.get("external_id") or "").strip()
    title = (row.get("title") or "").strip()
    brand, model = parse_brand_model(title)
    year = parse_year(row.get("year"))
    price_eur = row.get("price_eur")
    try:
        price_eur_i = int(price_eur) if price_eur is not None else None
    except (TypeError, ValueError):
        price_eur_i = None
    price_byn = eur_rate.eur_to_byn(price_eur_i) if eur_rate and price_eur_i is not None else None
    hp = extract_engine_power_hp(row)
    try:
        engine_l = float(row["engine_liters"]) if row.get("engine_liters") is not None else None
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

    return AutopliusMappedListing(
        external_id=external_id,
        source_url=(row.get("url") or None),
        title=title[:180],
        brand=brand,
        model=model,
        year=year,
        mileage=int(row["mileage_km"]) if row.get("mileage_km") is not None else None,
        price_eur=price_eur_i,
        price_byn=price_byn,
        city=(row.get("city") or None),
        body_type=(row.get("body_type") or None),
        engine_type=(row.get("fuel") or None),
        transmission_type=(row.get("transmission") or None),
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
