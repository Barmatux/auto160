"""Check whether an av.by listing is still publicly available (no auth)."""

from __future__ import annotations

import enum

from curl_cffi import requests


class OfferCheckResult(str, enum.Enum):
    active = "active"
    removed = "removed"
    unknown = "unknown"


def build_avby_public_url(avby_id: int, source_url: str | None = None) -> str:
    url = (source_url or "").strip()
    if url:
        return url
    return f"https://cars.av.by/{avby_id}"


def check_avby_offer_public(avby_id: int, source_url: str | None = None) -> OfferCheckResult:
    """Return whether the advert is active on av.by.

    Uses the public HTML page (source_url). The JSON API
    ``/offer-types/cars/offers/{id}`` returns 404 without auth even for active
    listings, so it cannot be used here.
    """
    url = build_avby_public_url(avby_id, source_url)
    try:
        resp = requests.get(url, impersonate="chrome124", timeout=25, allow_redirects=True)
    except Exception:
        return OfferCheckResult.unknown

    text = resp.text or ""
    lowered = text.lower()
    id_str = str(avby_id)

    if resp.status_code == 404 or "не найден" in lowered:
        return OfferCheckResult.removed

    if resp.status_code != 200:
        return OfferCheckResult.unknown

    if id_str not in text:
        return OfferCheckResult.removed

    if '"name":"active"' in text or '"status":"active"' in text:
        return OfferCheckResult.active

    return OfferCheckResult.removed
