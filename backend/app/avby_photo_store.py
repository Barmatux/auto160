"""Download av.by listing photos and store them in the Autoplius S3 bucket under ``avby/``."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from botocore.exceptions import BotoCoreError, ClientError

from app.storage import (
    autoplius_bucket,
    autoplius_object_exists,
    build_autoplius_media_url,
    put_autoplius_object,
)

logger = logging.getLogger(__name__)

AVBY_PHOTO_PREFIX = "avby"
MAX_PHOTOS_PER_LISTING = 20
_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Auto160/1.0; +https://auto160.ru/)",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Referer": "https://av.by/",
}


def is_avby_s3_media_url(url: str | None) -> bool:
    if not url:
        return False
    text = url.strip()
    return text.startswith("/media/autoplius?key=avby%") or "key=avby%2F" in text or "/media/autoplius?key=avby/" in text


def _guess_ext_and_content_type(url: str, content_type_header: str | None) -> tuple[str, str]:
    content_type = (content_type_header or "").split(";")[0].strip().lower()
    if content_type in {"image/jpeg", "image/png", "image/webp", "image/avif"}:
        if content_type == "image/jpeg":
            return ".jpg", content_type
        if content_type == "image/png":
            return ".png", content_type
        if content_type == "image/webp":
            return ".webp", content_type
        return ".avif", content_type
    path_ext = Path(urlparse(url).path).suffix.lower()
    if path_ext in {".jpg", ".jpeg"}:
        return ".jpg", "image/jpeg"
    if path_ext == ".png":
        return ".png", "image/png"
    if path_ext == ".webp":
        return ".webp", "image/webp"
    if path_ext == ".avif":
        return ".avif", "image/avif"
    guessed = mimetypes.guess_type(url)[0]
    if guessed:
        return Path(mimetypes.guess_extension(guessed) or ".jpg").suffix or ".jpg", guessed
    return ".jpg", "image/jpeg"


def _download_image(url: str, *, timeout: int = 25) -> tuple[bytes, str] | None:
    request = Request(url.strip(), headers=_DOWNLOAD_HEADERS)
    try:
        with urlopen(request, timeout=timeout) as response:
            data = response.read()
            content_type = response.headers.get("Content-Type", "")
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        logger.debug("avby photo download failed url=%s err=%s", url[:120], exc)
        return None
    if not data:
        return None
    return data, content_type


def _pick_photo_source_url(photo: dict[str, Any]) -> str | None:
    variants = photo.get("variants") if isinstance(photo.get("variants"), dict) else {}
    for key in ("big", "medium", "small", "extrasmall"):
        value = variants.get(key)
        if isinstance(value, str) and value.strip().startswith("http"):
            return value.strip()
    for key in ("big", "medium", "small", "extrasmall", "url"):
        value = photo.get(key)
        if isinstance(value, dict) and isinstance(value.get("url"), str) and value["url"].strip().startswith("http"):
            return value["url"].strip()
        if isinstance(value, str) and value.strip().startswith("http"):
            return value.strip()
    return None


def _storage_key(avby_id: int, index: int, ext: str) -> str:
    safe_ext = ext if ext.startswith(".") else f".{ext}"
    return f"{AVBY_PHOTO_PREFIX}/{int(avby_id)}/{index:03d}{safe_ext}"


def store_avby_listing_photos(
    avby_id: int,
    cover_photo_url: str | None,
    raw_photos: list[dict[str, Any]] | None,
    *,
    force: bool = False,
    max_photos: int = MAX_PHOTOS_PER_LISTING,
) -> tuple[str | None, list[dict[str, Any]] | None]:
    """Upload CDN photos into autoplius-media under ``avby/{id}/`` and return proxy URLs.

    On S3/config failure returns the original CDN payload unchanged.
    """
    if avby_id <= 0:
        return cover_photo_url, raw_photos

    if (
        not force
        and is_avby_s3_media_url(cover_photo_url)
        and isinstance(raw_photos, list)
        and raw_photos
        and all(is_avby_s3_media_url((p.get("url") if isinstance(p, dict) else None)) for p in raw_photos)
    ):
        return cover_photo_url, raw_photos

    source_urls: list[str] = []
    if isinstance(raw_photos, list):
        for photo in raw_photos:
            if not isinstance(photo, dict):
                continue
            url = _pick_photo_source_url(photo)
            if url and url not in source_urls:
                source_urls.append(url)
    if cover_photo_url and cover_photo_url.startswith("http") and cover_photo_url not in source_urls:
        source_urls.insert(0, cover_photo_url)

    if not source_urls:
        return cover_photo_url, raw_photos

    source_urls = source_urls[: max(1, int(max_photos))]
    stored_urls: list[str] = []
    try:
        for index, url in enumerate(source_urls):
            downloaded = _download_image(url)
            if downloaded is None:
                continue
            body, content_type_header = downloaded
            ext, content_type = _guess_ext_and_content_type(url, content_type_header)
            key = _storage_key(avby_id, index, ext)
            if force or not autoplius_object_exists(key):
                put_autoplius_object(key, body, content_type)
            stored_urls.append(build_autoplius_media_url(key))
    except RuntimeError as exc:
        logger.warning("avby photo S3 unavailable for avby_id=%s: %s", avby_id, exc)
        return cover_photo_url, raw_photos
    except (ClientError, BotoCoreError) as exc:
        logger.warning("avby photo upload failed avby_id=%s: %s", avby_id, exc)
        return cover_photo_url, raw_photos

    if not stored_urls:
        return cover_photo_url, raw_photos

    proxy_photos = [{"url": url, "main": index == 0} for index, url in enumerate(stored_urls)]
    return stored_urls[0][:500], proxy_photos
