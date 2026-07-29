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
