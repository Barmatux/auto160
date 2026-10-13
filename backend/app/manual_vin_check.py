"""Admin «Ручная проверка»: ingest av.by listing/search URLs and run VIN/customs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import parse_qsl, unquote, urlparse

from curl_cffi import requests
from sqlalchemy.orm import Session

from app.avby_price import extract_price_byn_from_advert
from app.listing_catalog_link import link_listing_to_catalog
from app.listing_enrichment import perform_listing_vin_check
from app.listing_missing_byn import apply_import_byn_price_state
from app.models import CarListing, ListingStatus, User, UserRole
from app.security import hash_password


def _is_avby_s3_media_url(url: str | None) -> bool:
    """Local copy of avby_photo_store.is_avby_s3_media_url (avoids heavy storage import)."""
    if not url:
        return False
    text = url.strip()
    if "key=avby%2F" in text or "key=avby/" in text:
        return True
    return (
        text.startswith("/media/object?key=avby%")
        or text.startswith("/media/object?key=avby/")
        or text.startswith("/media/autoplius?key=avby%")
        or text.startswith("/media/autoplius?key=avby/")
    )

APPLY_URL = "https://web-api.av.by/offer-types/cars/filters/main/apply"
DEFAULT_SORT_NEWEST = 4
PRESERVE_ON_UPDATE_FIELDS = frozenset({"vin", "vin_fetched_at", "manual_vin_checked_at"})

UrlKind = Literal["listing", "search"]

_AVBY_HOST_RE = re.compile(r"(?:^|\.)av\.by$", re.IGNORECASE)
_INITIAL_VALUE_RE = re.compile(
    r'"initialValue"\s*:\s*"(?P<value>(?:\\.|[^"\\])*)"',
)


class ManualVinCheckError(Exception):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ParsedAvbyUrl:
    kind: UrlKind
    normalized_url: str
    listing_id: int | None = None
    filter_query: str = ""
    page: int = 1


@dataclass
class ManualVinCheckItemResult:
    listing_id: int
    avby_id: int | None = None
    created: bool = False
    vin: str | None = None
    vin_error: str | None = None
    release_date: str | None = None
    customs_found: bool | None = None
    customs_error: str | None = None


@dataclass
class ManualVinCheckRunResult:
    kind: UrlKind
    url: str
    advert_count: int = 0
    items: list[ManualVinCheckItemResult] = field(default_factory=list)
    error: str | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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


def _to_num(raw: str) -> Any:
    text = raw.strip()
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    return text


def _parse_avby_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def normalize_avby_url(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise ManualVinCheckError("Введите ссылку на объявление или поиск av.by")
    if not re.match(r"^https?://", text, re.IGNORECASE):
        text = "https://" + text
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if not host or not _AVBY_HOST_RE.search(host):
        raise ManualVinCheckError("Ссылка должна вести на av.by (cars.av.by)")
    return text


def parse_avby_url(raw: str) -> ParsedAvbyUrl:
    url = normalize_avby_url(raw)
    parsed = urlparse(url)
    path = (parsed.path or "/").strip("/")
    parts = [p for p in path.split("/") if p]
    query = parsed.query or ""

    page = 1
    for key, value in parse_qsl(query, keep_blank_values=False):
        if key == "page":
            page = max(1, _to_int(value) or 1)

    if parts and parts[0].casefold() == "filter":
        return ParsedAvbyUrl(
            kind="search",
            normalized_url=url,
            filter_query=query,
            page=page,
        )

    # /brand/model/123456789 or /123456789 — trailing numeric id is a listing card.
    if parts and parts[-1].isdigit() and len(parts[-1]) >= 5:
        return ParsedAvbyUrl(
            kind="listing",
            normalized_url=url,
            listing_id=int(parts[-1]),
            page=page,
        )

    # Brand/model landing or other search surfaces → resolve via page initialValue / query
    return ParsedAvbyUrl(
        kind="search",
        normalized_url=url,
        filter_query=query,
        page=page,
    )


def parse_filter_query_to_properties(query: str) -> tuple[list[dict[str, Any]], int]:
    pairs = parse_qsl(query, keep_blank_values=False)
    sorting = DEFAULT_SORT_NEWEST
    brands: dict[int, dict[str, Any]] = {}
    ranges: dict[str, dict[str, Any]] = {}
    arrays: dict[str, list[Any]] = {}
    scalars: dict[str, Any] = {}

    for key, raw in pairs:
        key = unquote(key)
        val = _to_num(raw)
        if key == "sort":
            sorting = int(val) if isinstance(val, int) else DEFAULT_SORT_NEWEST
            continue
        m = re.fullmatch(r"brands\[(\d+)\]\[(\w+)\]", key)
        if m:
            brands.setdefault(int(m.group(1)), {})[m.group(2)] = val
            continue
        m = re.fullmatch(r"(\w+)\[(min|max)\]", key)
        if m:
            ranges.setdefault(m.group(1), {})[m.group(2)] = val
            continue
        m = re.fullmatch(r"(\w+)\[(\d*)\]", key)
        if m:
            arrays.setdefault(m.group(1), []).append(val)
            continue
        if key in scalars:
            prev = scalars[key]
            scalars[key] = (prev if isinstance(prev, list) else [prev]) + [val]
        else:
            scalars[key] = val

    properties: list[dict[str, Any]] = []
    if "price_currency" not in scalars:
        properties.append({"name": "price_currency", "value": 2})
    if brands:
        properties.append({"name": "brands", "value": [brands[i] for i in sorted(brands)]})
    for name, rng in ranges.items():
        properties.append({"name": name, "value": rng})
    for name, vals in arrays.items():
        properties.append({"name": name, "value": vals})
    for name, val in scalars.items():
        properties.append({"name": name, "value": val})
    return properties, sorting


def _request_headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ru-RU,ru;q=0.9",
        "Origin": "https://av.by",
        "Referer": referer or "https://cars.av.by/filter",
    }


def _fetch_html(url: str) -> str:
    response = requests.get(
        url,
        impersonate="chrome124",
        timeout=45,
        headers={
            "User-Agent": _request_headers(url)["User-Agent"],
            "Accept-Language": "ru-RU,ru;q=0.9",
        },
    )
    if response.status_code >= 400:
        raise ManualVinCheckError(
            f"Не удалось открыть страницу av.by (HTTP {response.status_code})",
            status_code=502,
        )
    return response.text


def _extract_json_object_at(text: str, start: int) -> dict[str, Any] | None:
    if start < 0 or start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, min(len(text), start + 800_000)):
        ch = text[index]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    payload = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return None
                return payload if isinstance(payload, dict) else None
    return None


def extract_advert_from_listing_html(html: str, avby_id: int) -> dict[str, Any] | None:
    needle = f'{{"id":{avby_id}'
    start = html.find(needle)
    if start < 0:
        needle = f'{{"id": {avby_id}'
        start = html.find(needle)
    if start < 0:
        return None
    payload = _extract_json_object_at(html, start)
    if not payload:
        return None
    if _to_int(payload.get("id")) != avby_id:
        return None
    if "properties" not in payload and "publicUrl" not in payload:
        return None
    # Public card may use refreshedAt instead of renewedAt from apply API.
    if not payload.get("renewedAt") and payload.get("refreshedAt"):
        payload = dict(payload)
        payload["renewedAt"] = payload.get("refreshedAt")
    return payload


def extract_initial_value_from_html(html: str) -> str | None:
    match = _INITIAL_VALUE_RE.search(html or "")
    if not match:
        return None
    raw = match.group("value")
    try:
        return json.loads(f'"{raw}"')
    except json.JSONDecodeError:
        return raw.replace("\\u0026", "&").replace("\\/", "/")


def fetch_listing_advert(avby_id: int, *, page_url: str | None = None) -> dict[str, Any]:
    candidates: list[str] = []
    primary = (page_url or "").strip()
    if primary:
        candidates.append(primary)
    fallback = f"https://cars.av.by/{avby_id}"
    if fallback not in candidates:
        candidates.append(fallback)

    last_error: str | None = None
    for url in candidates:
        try:
            html = _fetch_html(url)
        except ManualVinCheckError as exc:
            last_error = str(exc)
            continue
        advert = extract_advert_from_listing_html(html, avby_id)
        if advert is not None:
            return advert
        last_error = f"Не удалось извлечь объявление #{avby_id} со страницы av.by"

    raise ManualVinCheckError(last_error or f"Объявление #{avby_id} не найдено", status_code=502)


def resolve_search_filter_query(parsed: ParsedAvbyUrl) -> str:
    if parsed.filter_query.strip():
        return parsed.filter_query
    html = _fetch_html(parsed.normalized_url)
    initial = extract_initial_value_from_html(html)
    if not initial:
        raise ManualVinCheckError(
            "Не удалось определить фильтры поиска на странице av.by",
            status_code=502,
        )
    return initial


def fetch_search_adverts(parsed: ParsedAvbyUrl) -> list[dict[str, Any]]:
    query = resolve_search_filter_query(parsed)
    properties, sorting = parse_filter_query_to_properties(query)
    # Prefer newest→oldest unless user explicitly chose another sort in the URL.
    if "sort=" not in query:
        sorting = DEFAULT_SORT_NEWEST
    payload = {
        "page": parsed.page,
        "sorting": sorting,
        "properties": properties,
    }
    response = requests.post(
        APPLY_URL,
        impersonate="chrome124",
        timeout=45,
        headers={
            **_request_headers(parsed.normalized_url),
            "Content-Type": "application/json",
        },
        json=payload,
    )
    if response.status_code >= 400:
        raise ManualVinCheckError(
            f"Ошибка API поиска av.by (HTTP {response.status_code})",
            status_code=502,
        )
    data = response.json()
    adverts = data.get("adverts") if isinstance(data, dict) else None
    if not isinstance(adverts, list):
        raise ManualVinCheckError("Пустой ответ поиска av.by", status_code=502)
    return [item for item in adverts if isinstance(item, dict)]


def _extract_properties_map(advert: dict[str, Any]) -> dict[str, Any]:
    props_map: dict[str, Any] = {}
    for prop in advert.get("properties") or []:
        if not isinstance(prop, dict):
            continue
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
        variants: dict[str, str] = {}
        for variant_name in ("big", "medium", "small", "extrasmall"):
            variant = photo.get(variant_name)
            if isinstance(variant, dict) and variant.get("url"):
                variants[variant_name] = str(variant.get("url"))
        if not variants:
            continue
        normalized_photos.append(
            {
                "id": photo.get("id"),
                "main": bool(photo.get("main")),
                "mimeType": photo.get("mimeType"),
                "variants": variants,
            }
        )
        if cover_url is None and photo.get("main"):
            cover_url = variants.get("big") or variants.get("medium") or variants.get("small")
    if cover_url is None:
        for photo in normalized_photos:
            variants = photo.get("variants") or {}
            cover_url = variants.get("big") or variants.get("medium") or variants.get("small")
            if cover_url:
                break
    return cover_url, normalized_photos


def advert_to_listing_payload(advert: dict[str, Any]) -> dict[str, Any] | None:
    avby_id = _to_int(advert.get("id"))
    if avby_id is None:
        return None

    props = _extract_properties_map(advert)
    meta = advert.get("metadata") if isinstance(advert.get("metadata"), dict) else {}
    fallback_brand = str(meta.get("brandSlug") or "").replace("-", " ").strip()
    fallback_model = str(meta.get("modelSlug") or "").replace("-", " ").strip()
    brand = (props.get("brand") or fallback_brand or "").strip()
    model = (props.get("model") or fallback_model or "").strip()
    year = _to_int(advert.get("year") or props.get("year"))
    if not brand or not model or year is None:
        return None

    mileage = _to_int(props.get("mileage_km")) or 0
    price_byn = extract_price_byn_from_advert(advert)
    price_byn_missing = price_byn is None
    city = (advert.get("shortLocationName") or advert.get("locationName") or "Не указан").strip()
    public_url = (advert.get("publicUrl") or "").strip()
    cover_photo_url, raw_photos = _extract_photo_urls(advert)

    raw_title = meta.get("title")
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

    renewed = advert.get("renewedAt") or advert.get("refreshedAt")
    return {
        "avby_id": avby_id,
        "title": title[:180],
        "brand": brand[:80],
        "model": model[:80],
        "generation": str(props.get("generation") or "").strip()[:120] or None,
        "year": year,
        "mileage": mileage,
        "price": price_byn,
        "price_byn_missing": price_byn_missing,
        "city": city[:80],
        "body_type": str(props.get("body_type") or "").strip()[:60] or None,
        "drive_type": str(props.get("drive_type") or "").strip()[:40] or None,
        "transmission_type": str(props.get("transmission_type") or "").strip()[:40] or None,
        "engine_type": str(props.get("engine_type") or "").strip()[:40] or None,
        "engine_capacity_l": _to_float(props.get("engine_capacity")),
        "engine_power_hp": _to_int(props.get("engine_power")),
        "vin_indicated": _to_bool(props.get("vin_indicated")),
        "seller_name": (advert.get("sellerName") or advert.get("organizationTitle") or "").strip()[:120]
        or None,
        "organization_id": _to_int(advert.get("organizationId")),
        "source_url": public_url[:500] or None,
        "cover_photo_url": cover_photo_url[:500] if cover_photo_url else None,
        "raw_photos": raw_photos or None,
        "description": description,
        "avby_published_at": _parse_avby_datetime(advert.get("publishedAt")),
        "avby_renewed_at": _parse_avby_datetime(renewed),
    }


def _ensure_importer_user(db: Session) -> User:
    user = db.query(User).filter(User.role == UserRole.admin).order_by(User.id.asc()).first()
    if user:
        return user
    user = db.query(User).order_by(User.id.asc()).first()
    if user:
        return user
    created = User(
        username="avby_importer",
        email="avby_importer@auto160.local",
        name="AV.BY Importer",
        role=UserRole.seller,
        password_hash=hash_password("change_me_now_123"),
    )
    db.add(created)
    db.commit()
    db.refresh(created)
    return created


def upsert_advert_listing(db: Session, advert: dict[str, Any]) -> tuple[CarListing, bool]:
    payload = advert_to_listing_payload(advert)
    if payload is None:
        raise ManualVinCheckError("Не удалось разобрать объявление av.by")

    avby_id = int(payload.pop("avby_id"))
    price_byn_missing = bool(payload.pop("price_byn_missing", False))
    price_byn = payload.get("price")
    seller = _ensure_importer_user(db)

    existing = (
        db.query(CarListing)
        .filter(CarListing.avby_id == avby_id)
        .order_by(CarListing.id.asc())
        .first()
    )
    if existing is None:
        existing = (
            db.query(CarListing)
            .filter(CarListing.source == "av.by", CarListing.external_id == str(avby_id))
            .order_by(CarListing.id.asc())
            .first()
        )

    if existing:
        keep_photos = _is_avby_s3_media_url(existing.cover_photo_url) and isinstance(
            existing.raw_photos, list
        ) and existing.raw_photos
        existing.avby_id = avby_id
        existing.source = "av.by"
        existing.external_id = str(avby_id)
        for field, value in payload.items():
            if field in PRESERVE_ON_UPDATE_FIELDS:
                continue
            if keep_photos and field in ("cover_photo_url", "raw_photos"):
                continue
            setattr(existing, field, value)
        apply_import_byn_price_state(
            existing,
            price_byn=price_byn,
            price_byn_missing=price_byn_missing,
        )
        existing.manual_vin_checked_at = _utc_now()
        db.add(existing)
        link_listing_to_catalog(db, existing, commit=False)
        db.commit()
        db.refresh(existing)
        return existing, False

    listing = CarListing(
        seller_id=seller.id,
        avby_id=avby_id,
        source="av.by",
        external_id=str(avby_id),
        status=ListingStatus.draft if price_byn_missing else ListingStatus.published,
        price_byn_missing=price_byn_missing,
        manual_vin_checked_at=_utc_now(),
        **payload,
    )
    db.add(listing)
    db.flush()
    link_listing_to_catalog(db, listing, commit=False)
    db.commit()
    db.refresh(listing)
    return listing, True


def collect_adverts_for_url(raw_url: str) -> tuple[ParsedAvbyUrl, list[dict[str, Any]]]:
    parsed = parse_avby_url(raw_url)
    if parsed.kind == "listing":
        assert parsed.listing_id is not None
        advert = fetch_listing_advert(parsed.listing_id, page_url=parsed.normalized_url)
        return parsed, [advert]
    adverts = fetch_search_adverts(parsed)
    return parsed, adverts


def run_manual_vin_check_from_url(
    db: Session,
    raw_url: str,
    *,
    run_vin_checks: bool = True,
) -> ManualVinCheckRunResult:
    parsed, adverts = collect_adverts_for_url(raw_url)
    result = ManualVinCheckRunResult(
        kind=parsed.kind,
        url=parsed.normalized_url,
        advert_count=len(adverts),
    )
    if not adverts:
        result.error = "На странице не найдено объявлений"
        return result

    for advert in adverts:
        listing, created = upsert_advert_listing(db, advert)
        item = ManualVinCheckItemResult(
            listing_id=listing.id,
            avby_id=listing.avby_id,
            created=created,
        )
        if run_vin_checks:
            check = perform_listing_vin_check(db, listing, allow_inactive=True)
            item.vin = check.vin
            item.vin_error = check.vin_error
            item.release_date = check.release_date
            item.customs_found = check.customs_found
            item.customs_error = check.customs_error
        result.items.append(item)
    return result


def paginate_manual_vin_check_listings(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 21,
) -> tuple[list[CarListing], int]:
    query = (
        db.query(CarListing)
        .filter(CarListing.manual_vin_checked_at.isnot(None))
        .order_by(CarListing.manual_vin_checked_at.desc(), CarListing.id.desc())
    )
    total = query.count()
    offset = max(0, (page - 1) * page_size)
    rows = query.offset(offset).limit(page_size).all()
    return rows, total
