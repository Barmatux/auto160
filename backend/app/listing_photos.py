"""Resolve listing preview photos from av.by URLs with fallbacks."""

from __future__ import annotations

from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.models import CarListing
from app.storage import is_remote_catalog_image_url, normalize_display_image_url

_AVCdn_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Auto160/1.0; +https://av.by/)",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://av.by/",
}


def listing_photo_candidate_urls(listing: CarListing) -> list[str]:
    candidates: list[str] = []

    def add(url: str | None) -> None:
        if not url:
            return
        cleaned = url.strip()
        if cleaned and cleaned not in candidates:
            candidates.append(cleaned)

    add(listing.cover_photo_url)
    raw_photos = listing.raw_photos
    if not isinstance(raw_photos, list):
        return candidates

    main_variants: list[str] = []
    other_variants: list[str] = []
    for photo in raw_photos:
        if isinstance(photo, str):
            other_variants.append(photo)
            continue
        if not isinstance(photo, dict):
            continue

        add(photo.get("url") if isinstance(photo.get("url"), str) else None)

        variants = photo.get("variants")
        if isinstance(variants, dict):
            bucket = main_variants if photo.get("main") else other_variants
            for key in ("big", "medium", "small", "extrasmall"):
                variant_url = variants.get(key)
                if isinstance(variant_url, str):
                    bucket.append(variant_url)

        for key in ("big", "medium", "small", "extrasmall"):
            variant = photo.get(key)
            if isinstance(variant, dict):
                add(variant.get("url") if isinstance(variant.get("url"), str) else None)
            elif isinstance(variant, str):
                other_variants.append(variant)

    for url in main_variants + other_variants:
        add(url)
    return candidates


def _remote_image_get_available(url: str) -> bool:
    request = Request(
        url.strip(),
        headers={**_AVCdn_HEADERS, "Range": "bytes=0-0"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=5) as response:
            status = int(getattr(response, "status", None) or response.getcode())
            return 200 <= status < 300 or status == 206
    except HTTPError as exc:
        return exc.code in (200, 206)
    except (URLError, TimeoutError, ValueError, OSError):
        return False


@lru_cache(maxsize=1024)
def remote_avby_image_available(url: str) -> bool:
    if not is_remote_catalog_image_url(url):
        return True
    request = Request(url.strip(), headers=_AVCdn_HEADERS, method="HEAD")
    try:
        with urlopen(request, timeout=5) as response:
            status = getattr(response, "status", None) or response.getcode()
            return 200 <= int(status) < 300
    except HTTPError as exc:
        if exc.code == 405:
            return _remote_image_get_available(url)
        return 200 <= exc.code < 300
    except (URLError, TimeoutError, ValueError, OSError):
        return _remote_image_get_available(url)


def _pick_photo_display_url(photo: dict | str) -> str | None:
    if isinstance(photo, str):
        cleaned = photo.strip()
        return cleaned or None
    if not isinstance(photo, dict):
        return None
    variants = photo.get("variants")
    if isinstance(variants, dict):
        for key in ("big", "medium", "small", "extrasmall"):
            url = variants.get(key)
            if isinstance(url, str) and url.strip():
                return url.strip()
    if isinstance(photo.get("url"), str) and photo["url"].strip():
        return photo["url"].strip()
    for key in ("big", "medium", "small", "extrasmall"):
        variant = photo.get(key)
        if isinstance(variant, dict):
            url = variant.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
        elif isinstance(variant, str) and variant.strip():
            return variant.strip()
    return None


def resolve_listing_gallery_urls(listing: CarListing, *, verify_remote: bool = False) -> list[str]:
    """One proxied display URL per photo for listing detail gallery."""
    raw_urls: list[str] = []
    raw_photos = listing.raw_photos
    if isinstance(raw_photos, list):
        for photo in raw_photos:
            picked = _pick_photo_display_url(photo)
            if picked:
                raw_urls.append(picked)

    if listing.cover_photo_url:
        cover = listing.cover_photo_url.strip()
        if cover:
            if cover in raw_urls:
                raw_urls.remove(cover)
            raw_urls.insert(0, cover)

    if not raw_urls:
        cover = pick_listing_cover_url(listing, verify_remote=verify_remote)
        return [cover] if cover else []

    gallery: list[str] = []
    seen_raw: set[str] = set()
    for candidate in raw_urls:
        if candidate in seen_raw:
            continue
        seen_raw.add(candidate)
        if verify_remote and is_remote_catalog_image_url(candidate) and not remote_avby_image_available(candidate):
            continue
        normalized = normalize_display_image_url(candidate) or candidate
        if normalized:
            gallery.append(normalized)
    return gallery


def pick_listing_cover_url(listing: CarListing, *, verify_remote: bool = True) -> str | None:
    for candidate in listing_photo_candidate_urls(listing):
        if verify_remote and is_remote_catalog_image_url(candidate) and not remote_avby_image_available(candidate):
            continue
        normalized = normalize_display_image_url(candidate) or candidate
        if normalized:
            return normalized
    return None


def resolve_listing_cover_urls(listings: list[CarListing]) -> dict[int, str]:
    return {
        listing.id: cover
        for listing in listings
        if (cover := pick_listing_cover_url(listing))
    }
