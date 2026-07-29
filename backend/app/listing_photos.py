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
        return 200 <= exc.code < 300
    except (URLError, TimeoutError, ValueError, OSError):
        return False


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
