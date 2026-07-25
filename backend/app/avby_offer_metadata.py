"""Fetch VIN metadata from authenticated av.by offer detail API.

Task #84: during sync call ``GET /offer-types/cars/offers/{id}`` under a service
account and persist ``vin``, ``vin_indicated``, ``vin_fetched_at`` on listings.

This is separate from the paid ``GET .../offers/{id}/vin`` endpoint (see
``app.avby_vin``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from curl_cffi import requests
from sqlalchemy.orm import Session

from app.avby_accounts import list_active_auth_accounts, select_auth_account
from app.avby_session import AvbySessionError, get_avby_session
from app.customs_vin import normalize_vin, vin_is_valid
from app.models import CarListing

AVBY_BASE = "https://web-api.av.by"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class AvbyOfferMetadataError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class OfferVinMetadata:
    vin: str | None = None
    vin_indicated: bool | None = None


@dataclass
class OfferMetadataApplyResult:
    fetched: bool = False
    vin_saved: bool = False
    indicated_updated: bool = False
    error: str | None = None


@dataclass
class OfferMetadataStats:
    eligible: int = 0
    attempted: int = 0
    fetched: int = 0
    vin_saved: int = 0
    indicated_updated: int = 0
    skipped_has_vin: int = 0
    skipped_no_account: int = 0
    skipped_limit: int = 0
    errors: list[str] = field(default_factory=list)


def listing_has_saved_vin(listing: CarListing) -> bool:
    return len((listing.vin or "").strip()) == 17


def _utc_now() -> datetime:
    return datetime.utcnow()


def _avby_headers(api_key: str, token: str) -> dict[str, str]:
    return {
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-device-type": "web.desktop",
        "Origin": "https://av.by",
        "Referer": "https://av.by/",
        "X-Api-Key": api_key,
        "Authorization": f"Bearer {token}",
    }


def _extract_properties_map(offer: dict[str, Any]) -> dict[str, Any]:
    props_map: dict[str, Any] = {}
    for prop in offer.get("properties") or []:
        if not isinstance(prop, dict):
            continue
        name = prop.get("name")
        if not name:
            continue
        props_map[name] = prop.get("value")
    return props_map


def _coerce_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "да"}:
            return True
        if lowered in {"false", "0", "no", "нет"}:
            return False
    return None


def extract_vin_indicated(offer: dict[str, Any]) -> bool | None:
    props = _extract_properties_map(offer)
    indicated = _coerce_bool(props.get("vin_indicated"))
    if indicated is not None:
        return indicated

    vin_info = offer.get("vinInfo")
    if isinstance(vin_info, dict):
        for key in ("indicated", "isIndicated", "vinIndicated", "hasVin", "isVinIndicated"):
            if key in vin_info:
                return _coerce_bool(vin_info[key])
    return None


def extract_full_vin(offer: dict[str, Any]) -> str | None:
    candidates: list[str] = []

    for key in ("vin", "vinCode", "vinNumber"):
        value = offer.get(key)
        if value:
            candidates.append(str(value))

    props = _extract_properties_map(offer)
    for key in ("vin", "vin_code", "vin_number", "vinCode"):
        value = props.get(key)
        if value:
            candidates.append(str(value))

    vin_info = offer.get("vinInfo")
    if isinstance(vin_info, dict):
        for key in ("vin", "value", "fullVin", "vinCode"):
            value = vin_info.get(key)
            if value:
                candidates.append(str(value))
    elif isinstance(vin_info, str):
        candidates.append(vin_info)

    for raw in candidates:
        vin = normalize_vin(raw)
        if vin_is_valid(vin):
            return vin
    return None


def extract_offer_vin_metadata(offer: dict[str, Any]) -> OfferVinMetadata:
    return OfferVinMetadata(
        vin=extract_full_vin(offer),
        vin_indicated=extract_vin_indicated(offer),
    )


def fetch_authenticated_offer(api_key: str, token: str, avby_id: int) -> dict[str, Any]:
    resp = requests.get(
        f"{AVBY_BASE}/offer-types/cars/offers/{avby_id}",
        impersonate="chrome124",
        timeout=30,
        headers=_avby_headers(api_key, token),
    )
    if resp.status_code == 404:
        raise AvbyOfferMetadataError("offer not found", status_code=404)
    if resp.status_code in (401, 403):
        raise AvbyOfferMetadataError(
            f"auth failed: HTTP {resp.status_code}",
            status_code=resp.status_code,
        )
    if resp.status_code == 429:
        raise AvbyOfferMetadataError("rate limited", status_code=429)
    if resp.status_code != 200:
        raise AvbyOfferMetadataError(
            f"offer request failed: HTTP {resp.status_code} {resp.text[:200]}",
            status_code=502,
        )
    payload = resp.json()
    if not isinstance(payload, dict):
        raise AvbyOfferMetadataError("invalid offer payload", status_code=502)
    return payload


def apply_offer_vin_metadata(listing: CarListing, offer: dict[str, Any]) -> OfferMetadataApplyResult:
    metadata = extract_offer_vin_metadata(offer)
    result = OfferMetadataApplyResult(fetched=True)

    if metadata.vin_indicated is not None:
        listing.vin_indicated = metadata.vin_indicated
        result.indicated_updated = True

    if metadata.vin and not listing_has_saved_vin(listing):
        listing.vin = metadata.vin
        listing.vin_fetched_at = _utc_now()
        if listing.vin_indicated is None:
            listing.vin_indicated = True
        result.vin_saved = True
    elif not listing.vin_fetched_at:
        listing.vin_fetched_at = _utc_now()

    return result


def fetch_and_apply_offer_vin_metadata(db: Session, listing: CarListing) -> OfferMetadataApplyResult:
    if not listing.avby_id:
        return OfferMetadataApplyResult(error="listing has no av.by id")
    if listing_has_saved_vin(listing):
        return OfferMetadataApplyResult()

    pool = list_active_auth_accounts(db)
    if not pool:
        return OfferMetadataApplyResult(error="no active auth accounts")

    tried: set[int] = set()
    last_error: str | None = None

    while True:
        account = select_auth_account(db, exclude_ids=tried)
        if account is None:
            return OfferMetadataApplyResult(error=last_error or "no auth accounts left")

        tried.add(account.id)
        try:
            session = get_avby_session(db, account)
        except AvbySessionError as exc:
            last_error = str(exc)
            account.error_message = last_error[:500]
            db.commit()
            continue

        try:
            offer = fetch_authenticated_offer(session.api_key, session.token, listing.avby_id)
        except AvbyOfferMetadataError as exc:
            last_error = str(exc)
            account.error_message = last_error[:500]
            db.commit()
            if exc.status_code in (401, 403, 429) and len(tried) < len(pool):
                continue
            return OfferMetadataApplyResult(error=last_error)

        account.error_message = None
        result = apply_offer_vin_metadata(listing, offer)
        db.commit()
        db.refresh(listing)
        return result


def enrich_listings_vin_metadata(
    db: Session,
    listings: list[CarListing],
    *,
    limit: int | None = 100,
) -> OfferMetadataStats:
    stats = OfferMetadataStats()
    if not listings:
        return stats

    pool = list_active_auth_accounts(db)
    if not pool:
        stats.skipped_no_account = sum(
            1 for listing in listings if listing.avby_id and not listing_has_saved_vin(listing)
        )
        return stats

    tried: set[int] = set()
    session = None
    current_account = None
    processed = 0

    for listing in listings:
        if not listing.avby_id:
            continue
        if listing_has_saved_vin(listing):
            stats.skipped_has_vin += 1
            continue

        stats.eligible += 1
        if limit is not None and processed >= limit:
            stats.skipped_limit += 1
            continue

        stats.attempted += 1
        applied = False
        while not applied:
            if session is None or current_account is None:
                current_account = select_auth_account(db, exclude_ids=tried)
                if current_account is None:
                    stats.errors.append("no active auth accounts left")
                    break
                tried.add(current_account.id)
                try:
                    session = get_avby_session(db, current_account)
                except AvbySessionError as exc:
                    current_account.error_message = str(exc)[:500]
                    db.commit()
                    session = None
                    current_account = None
                    if len(tried) >= len(pool):
                        stats.errors.append(str(exc))
                    continue

            try:
                offer = fetch_authenticated_offer(session.api_key, session.token, listing.avby_id)
            except AvbyOfferMetadataError as exc:
                current_account.error_message = str(exc)[:500]
                db.commit()
                if exc.status_code in (401, 403, 429):
                    session = None
                    current_account = None
                    if len(tried) < len(pool):
                        continue
                stats.errors.append(f"listing {listing.id}: {exc}")
                break

            result = apply_offer_vin_metadata(listing, offer)
            stats.fetched += 1
            if result.vin_saved:
                stats.vin_saved += 1
            if result.indicated_updated:
                stats.indicated_updated += 1
            current_account.error_message = None
            processed += 1
            applied = True

    if stats.fetched:
        db.commit()

    return stats
