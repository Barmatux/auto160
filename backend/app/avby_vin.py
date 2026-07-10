from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from curl_cffi import requests
from sqlalchemy.orm import Session

from app.avby_accounts import (
    consume_vin_check,
    list_active_vin_accounts,
    select_vin_account,
    vin_checks_remaining,
)
from app.avby_session import AvbySessionError, get_avby_session
from app.models import CarListing

AVBY_BASE = "https://web-api.av.by"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class AvbyVinError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ListingVinResult:
    vin: str | None
    source: str | None
    cached: bool
    checks_remaining: int | None
    fetched_at: datetime | None
    error: str | None = None


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


def _fetch_vin_from_avby(api_key: str, token: str, avby_id: int) -> str:
    resp = requests.get(
        f"{AVBY_BASE}/offer-types/cars/offers/{avby_id}/vin",
        impersonate="chrome124",
        timeout=30,
        headers=_avby_headers(api_key, token),
    )
    if resp.status_code != 200:
        raise AvbyVinError(
            f"av.by VIN request failed: HTTP {resp.status_code} {resp.text[:200]}",
            status_code=502,
        )
    vin = (resp.json().get("vin") or "").strip().upper()
    if not vin:
        raise AvbyVinError("av.by returned empty VIN", status_code=502)
    return vin


def get_or_fetch_listing_vin(db: Session, listing: CarListing) -> ListingVinResult:
    pool = list_active_vin_accounts(db)
    remaining_pool = sum(vin_checks_remaining(account) or 0 for account in pool)

    if listing.vin:
        first = pool[0] if pool else None
        return ListingVinResult(
            vin=listing.vin,
            source="database",
            cached=True,
            checks_remaining=remaining_pool if pool else None,
            fetched_at=listing.vin_fetched_at,
        )

    if not listing.avby_id:
        raise AvbyVinError("Listing has no av.by id", status_code=400)

    if not pool:
        raise AvbyVinError("No active VIN accounts in rotation (add verified account in admin)", status_code=503)

    tried: set[int] = set()
    last_error: str | None = None

    while True:
        account = select_vin_account(db, exclude_ids=tried)
        if account is None:
            detail = last_error or "Daily VIN limit reached on all accounts"
            raise AvbyVinError(detail, status_code=429 if last_error is None else 502)

        tried.add(account.id)
        try:
            session = get_avby_session(db, account)
        except AvbySessionError as exc:
            last_error = str(exc)
            account.error_message = last_error[:500]
            db.commit()
            continue

        try:
            vin = _fetch_vin_from_avby(session.api_key, session.token, listing.avby_id)
        except AvbyVinError as exc:
            last_error = str(exc)
            account.error_message = last_error[:500]
            db.commit()
            if exc.status_code == 429:
                continue
            if len(tried) < len(pool):
                continue
            raise

        listing.vin = vin
        listing.vin_fetched_at = _utc_now()
        if listing.vin_indicated is None:
            listing.vin_indicated = True
        account.error_message = None
        consume_vin_check(db, account)
        db.commit()
        db.refresh(listing)
        db.refresh(account)

        return ListingVinResult(
            vin=vin,
            source="avby",
            cached=False,
            checks_remaining=sum(vin_checks_remaining(row) or 0 for row in list_active_vin_accounts(db)),
            fetched_at=listing.vin_fetched_at,
        )
