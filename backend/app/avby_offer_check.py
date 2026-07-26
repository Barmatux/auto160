"""Check whether an av.by listing is still publicly available (no auth)."""

from __future__ import annotations

import enum
import re

from curl_cffi import requests

_INACTIVE_STATUSES = frozenset({"removed", "inactive", "sold", "blocked", "archived", "closed"})
_STATUS_AFTER_ID_RE = re.compile(r'(?P<id>\d{5,12})[^}]{0,500}"status"\s*:\s*"(?P<status>[a-z_]+)"', re.IGNORECASE)


class OfferCheckResult(str, enum.Enum):
    active = "active"
    removed = "removed"
    unknown = "unknown"


def build_avby_public_url(avby_id: int, source_url: str | None = None) -> str:
    url = (source_url or "").strip()
    if url:
        return url
    return f"https://cars.av.by/{avby_id}"


def extract_avby_advert_status(html: str, avby_id: int) -> str | None:
    """Parse embedded JSON status for a specific advert id on the listing page."""
    id_str = str(avby_id)
    for match in _STATUS_AFTER_ID_RE.finditer(html):
        if match.group("id") == id_str:
            return match.group("status").lower()
    return None


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

    status = extract_avby_advert_status(text, avby_id)
    if status == "active":
        return OfferCheckResult.active
    if status in _INACTIVE_STATUSES:
        return OfferCheckResult.removed

    # Inactive adverts stay on a public URL with an overlay badge.
    if "gallery__status" in text and "неактив" in lowered:
        return OfferCheckResult.removed

    if status is not None:
        return OfferCheckResult.removed

    return OfferCheckResult.unknown
