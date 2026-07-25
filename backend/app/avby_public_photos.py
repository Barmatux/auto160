"""Extract listing photos from public av.by HTML pages (no auth)."""

from __future__ import annotations

import json
import re
from typing import Any

from curl_cffi import requests

from app.avby_offer_check import OfferCheckResult, build_avby_public_url, check_avby_offer_public


def _pick_cover_url(photos: list[dict[str, Any]]) -> str | None:
    cover_url = None
    for photo in photos:
        if not isinstance(photo, dict):
            continue
        variants = photo.get("variants") if isinstance(photo.get("variants"), dict) else {}
        if not variants:
            for variant_name in ("big", "medium", "small", "extrasmall"):
                variant = photo.get(variant_name)
                if isinstance(variant, dict) and variant.get("url"):
                    variants[variant_name] = variant["url"]
        if photo.get("main") and variants:
            return variants.get("big") or variants.get("medium") or variants.get("small")
        if cover_url is None and variants:
            cover_url = variants.get("big") or variants.get("medium") or variants.get("small")
    return cover_url


def _normalize_photos(raw_photos: list[Any]) -> tuple[str | None, list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    for photo in raw_photos:
        if not isinstance(photo, dict):
            continue
        variants = {}
        for variant_name in ("big", "medium", "small", "extrasmall"):
            variant = photo.get(variant_name)
            if isinstance(variant, dict) and variant.get("url"):
                variants[variant_name] = variant["url"]
        normalized.append(
            {
                "id": photo.get("id"),
                "main": bool(photo.get("main")),
                "mimeType": photo.get("mimeType"),
                "variants": variants,
            }
        )
    return _pick_cover_url(normalized), normalized


def _extract_photos_json(html: str) -> list[dict[str, Any]] | None:
    match = re.search(r'"photos"\s*:\s*\[', html)
    if not match:
        return None
    start = html.index("[", match.start())
    try:
        payload, _ = json.JSONDecoder().raw_decode(html, start)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    return payload


def fetch_avby_public_photos(avby_id: int, source_url: str | None = None) -> tuple[str | None, list[dict[str, Any]]] | None:
    """Return (cover_url, raw_photos) or None if page unavailable / no photos."""
    status = check_avby_offer_public(avby_id, source_url)
    if status != OfferCheckResult.active:
        return None

    url = build_avby_public_url(avby_id, source_url)
    try:
        resp = requests.get(url, impersonate="chrome124", timeout=25, allow_redirects=True)
    except Exception:
        return None
    if resp.status_code != 200:
        return None

    raw = _extract_photos_json(resp.text or "")
    if not raw:
        return None
    cover, normalized = _normalize_photos(raw)
    if not normalized:
        return None
    return cover, normalized
