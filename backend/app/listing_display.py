"""Display helpers for listing detail pages."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from app.models import CarListing

_AVBY_TITLE_SUFFIX = re.compile(r"\s*\(av\.by\s*#\d+\)\s*", re.IGNORECASE)
_IMPORT_META_LINE = re.compile(
    r"^(?:AVBY_ID:\s*\d+|URL:\s*\S+|Источник:\s*av\.by)\s*$",
    re.IGNORECASE,
)
_LEGAL_ENTITY_MARKER = re.compile(
    r"(?ix)"
    r"(?:"
    r"\b(?:"
    r"ООО|OOO|ЗАО|ОАО|OAO|AO|ЧУП|ЧТУП|УП|ПЧУП|ТОО|ИП|IP|"
    r"LLC|LTD|Inc|Corp|Co\."
    r")\b"
    r"|«[^»]+»"
    r'|"[^"]+"'
    r")"
)


def listing_display_title(title: str | None) -> str:
    if not title:
        return ""
    return _AVBY_TITLE_SUFFIX.sub("", title).strip()


def listing_source_href(listing: CarListing) -> str | None:
    url = (listing.source_url or "").strip()
    if url:
        return url
    if listing.avby_id is not None:
        return f"https://cars.av.by/{listing.avby_id}"
    return None


def listing_source_label(source_url: str | None) -> str:
    if not source_url:
        return "av.by"
    parsed = urlparse(source_url.strip())
    host = (parsed.netloc or "av.by").removeprefix("www.")
    path = parsed.path.strip("/")
    if path:
        return f"{host}/{path}"
    return host


def listing_display_description(description: str | None) -> str:
    if not description:
        return ""
    lines = [line for line in description.splitlines() if not _IMPORT_META_LINE.match(line.strip())]
    return "\n".join(lines).strip()


def format_mileage_km(mileage: int | None) -> str:
    if mileage is None:
        return "—"
    return f"{mileage:,}".replace(",", " ")


def format_price_rub(price: float | int | None) -> str:
    if price is None:
        return "—"
    value = float(price)
    if value.is_integer():
        return f"{int(value):,}".replace(",", " ")
    formatted = f"{value:,.2f}".replace(",", " ")
    return formatted.replace(".", ",")


def listing_seller_label(seller_name: str | None) -> str:
    name = (seller_name or "").strip()
    if name and _LEGAL_ENTITY_MARKER.search(name):
        return name
    return "частное лицо"


def format_listing_spec_value(value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def _format_engine_capacity(capacity_l: float) -> str:
    rounded = round(capacity_l, 1)
    if abs(rounded - round(rounded)) < 0.05:
        return f"{rounded:.1f} л"
    return f"{rounded:g} л"


def listing_engine_summary(listing: CarListing) -> str | None:
    parts: list[str] = []
    if listing.engine_capacity_l is not None:
        parts.append(_format_engine_capacity(float(listing.engine_capacity_l)))
    if listing.engine_power_hp is not None:
        parts.append(f"{listing.engine_power_hp} л.с.")
    if listing.engine_type:
        parts.append(listing.engine_type.strip().lower())
    return ", ".join(parts) if parts else None
