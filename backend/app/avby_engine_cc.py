"""Resolve exact engine displacement (cm³) for Проверка / util eligibility.

Prefer Auto160 ``CatalogItem.engine_capacity_cc`` (backfilled from av.by dump).
Live av.by modification HTTP APIs are no longer used for inspection checks;
helpers below remain for offline/tests that score modifications.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from curl_cffi import requests

from app.catalog_engine_cc import engine_capacity_cc_from_liters, parse_engine_capacity_cc

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models import CarListing

logger = logging.getLogger(__name__)

_OFFER_URL = "https://api.av.by/offers/{avby_id}"
_GENERATION_MODS_URL = (
    "https://api.av.by/offer-types/cars/modifications-catalog/generations/{generation_id}/modifications"
)
_MOD_DETAIL_URL = (
    "https://api.av.by/offer-types/cars/modifications-catalog/modifications/{modification_id}"
)

_HP_IN_NAME_RE = re.compile(r"\((\d+)\s*л\.?\s*с", re.IGNORECASE)
_LITERS_IN_NAME_RE = re.compile(r"^(\d+[.,]\d+)")


@dataclass(frozen=True)
class EngineCcResolution:
    engine_cc: int | None
    approximate: bool
    modification_id: int | None = None
    source: str | None = None  # catalog | avby_mod | liters


def _headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://av.by/",
        "Origin": "https://av.by",
    }


def _get_json(url: str, *, retries: int = 3) -> Any | None:
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            response = requests.get(url, impersonate="chrome124", timeout=30, headers=_headers())
            if response.status_code == 429 and attempt + 1 < retries:
                time.sleep(1.2 * (attempt + 1))
                continue
            if response.status_code >= 400:
                return None
            return response.json()
        except Exception as exc:  # noqa: BLE001 — network/parse soft-fail
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(0.4 * (attempt + 1))
    if last_error:
        logger.info("avby engine_cc fetch failed for %s: %s", url, last_error)
    return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = re.sub(r"[^\d-]", "", str(value))
    if not text or text == "-":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().replace(",", ".")
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def _properties_map(advert: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for prop in advert.get("properties") or []:
        if isinstance(prop, dict) and prop.get("name"):
            out[str(prop["name"])] = prop.get("value")
    return out


def _hp_from_mod_name(name: str | None) -> int | None:
    if not name:
        return None
    match = _HP_IN_NAME_RE.search(name)
    return int(match.group(1)) if match else None


def _liters_from_mod_name(name: str | None) -> float | None:
    if not name:
        return None
    match = _LITERS_IN_NAME_RE.search(name.strip())
    if not match:
        return None
    return _to_float(match.group(1))


def _label_overlap(left: str, right: str) -> bool:
    a = _norm(left)
    b = _norm(right)
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a


def score_modification_for_listing(mod: dict[str, Any], *, props: dict[str, Any]) -> int:
    """Score how well a generation modification matches listing properties."""
    name = str(mod.get("name") or "")
    score = 0

    listing_hp = _to_int(props.get("engine_power"))
    mod_hp = _hp_from_mod_name(name)
    if listing_hp is not None and mod_hp is not None:
        if listing_hp == mod_hp:
            score += 60
        elif abs(listing_hp - mod_hp) <= 5:
            score += 20
        else:
            score -= 40

    listing_l = _to_float(props.get("engine_capacity"))
    mod_l = _liters_from_mod_name(name)
    if listing_l is not None and mod_l is not None:
        if abs(listing_l - mod_l) <= 0.06:
            score += 35
        elif abs(listing_l - mod_l) <= 0.15:
            score += 10
        else:
            score -= 25

    engine_type = _norm(props.get("engine_type"))
    mod_engine = _norm((mod.get("engineType") or {}).get("label") if isinstance(mod.get("engineType"), dict) else "")
    if engine_type and mod_engine:
        if _label_overlap(engine_type, mod_engine):
            score += 25
        else:
            score -= 30

    transmission = _norm(props.get("transmission_type"))
    mod_gear = _norm((mod.get("gearBoxType") or {}).get("label") if isinstance(mod.get("gearBoxType"), dict) else "")
    if transmission and mod_gear:
        if _label_overlap(transmission, mod_gear):
            score += 20
        else:
            score -= 15

    drive = _norm(props.get("drive_type"))
    mod_drive = _norm((mod.get("driveType") or {}).get("label") if isinstance(mod.get("driveType"), dict) else "")
    if drive and mod_drive:
        if _label_overlap(drive, mod_drive):
            score += 15
        else:
            score -= 10

    return score


def fetch_offer_json(avby_id: int) -> dict[str, Any] | None:
    data = _get_json(_OFFER_URL.format(avby_id=avby_id))
    return data if isinstance(data, dict) else None


def fetch_generation_modifications(generation_id: int) -> list[dict[str, Any]]:
    data = _get_json(_GENERATION_MODS_URL.format(generation_id=generation_id))
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def fetch_modification_detail(modification_id: int) -> dict[str, Any] | None:
    data = _get_json(_MOD_DETAIL_URL.format(modification_id=modification_id))
    return data if isinstance(data, dict) else None


def pick_best_modification(
    modifications: list[dict[str, Any]],
    *,
    props: dict[str, Any],
    min_score: int = 70,
) -> dict[str, Any] | None:
    ranked: list[tuple[int, dict[str, Any]]] = []
    for mod in modifications:
        score = score_modification_for_listing(mod, props=props)
        if score >= min_score and isinstance(mod.get("id"), int):
            ranked.append((score, mod))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1].get("id") or 0))
    best_score = ranked[0][0]
    # Ambiguous top scores with different ids → refuse exact match.
    top = [mod for score, mod in ranked if score == best_score]
    if len(top) > 1:
        return None
    return top[0]


def resolve_exact_engine_cc_from_offer(advert: dict[str, Any]) -> EngineCcResolution | None:
    meta = advert.get("metadata") if isinstance(advert.get("metadata"), dict) else {}
    generation_id = _to_int(meta.get("generationId"))
    if generation_id is None:
        return None
    props = _properties_map(advert)
    mods = fetch_generation_modifications(generation_id)
    best = pick_best_modification(mods, props=props)
    if best is None:
        return None
    mod_id = int(best["id"])
    detail = fetch_modification_detail(mod_id) or {}
    cc = parse_engine_capacity_cc(detail.get("engineCapacity"))
    if cc is None:
        return None
    return EngineCcResolution(
        engine_cc=cc,
        approximate=False,
        modification_id=mod_id,
        source="avby_mod",
    )


def _cc_from_catalog_item(item: "CatalogItem") -> int | None:
    from app.catalog_engine_cc import engine_capacity_cc_from_raw_specs

    if item.engine_capacity_cc is not None:
        try:
            cc = int(item.engine_capacity_cc)
        except (TypeError, ValueError):
            cc = None
        else:
            if 0 < cc <= 20000:
                return cc
    return engine_capacity_cc_from_raw_specs(
        item.raw_specs if isinstance(item.raw_specs, dict) else None
    )


def _catalog_candidates_for_listing(db: "Session", listing: "CarListing") -> list["CatalogItem"]:
    """Match candidates from our CatalogItem table (no live av.by calls)."""
    from app.catalog_visibility import apply_visible_catalog_filter
    from app.listing_catalog_link import canonical_model_name
    from app.models import CatalogItem

    make = (listing.brand or "").strip()
    model = canonical_model_name(listing.model)
    if not make or not model:
        return []
    return (
        apply_visible_catalog_filter(
            db.query(CatalogItem).filter(
                CatalogItem.source_site == "av.by",
                CatalogItem.make.ilike(make),
                CatalogItem.model == model,
            )
        )
        .order_by(CatalogItem.year_from.desc(), CatalogItem.id.asc())
        .all()
    )


def resolve_engine_cc_for_listing(
    db: "Session",
    listing: "CarListing | None",
    *,
    engine_capacity_l: float | None = None,
    advert: dict[str, Any] | None = None,
) -> EngineCcResolution:
    """Prefer our CatalogItem cm³; fall back to liters×1000 as approximate.

    Live av.by modification APIs are not used — exact capacity comes from
    ``catalog_items.engine_capacity_cc`` / raw_specs after matching the listing.
    ``advert`` is accepted for call-site compatibility and ignored.
    """
    del advert  # kept for signature compatibility; catalog-only resolution

    from app.listing_catalog_link import find_best_catalog_item, score_listing_catalog_match, MIN_LINK_SCORE
    from app.models import CatalogItem

    liters = engine_capacity_l
    if liters is None and listing is not None and listing.engine_capacity_l is not None:
        try:
            liters = float(listing.engine_capacity_l)
        except (TypeError, ValueError):
            liters = None

    item: CatalogItem | None = None
    if listing is not None and listing.catalog_item_id:
        linked = db.get(CatalogItem, listing.catalog_item_id)
        if linked is not None and score_listing_catalog_match(listing, linked) >= MIN_LINK_SCORE:
            item = linked

    if item is None and listing is not None:
        item = find_best_catalog_item(listing, _catalog_candidates_for_listing(db, listing))

    if item is not None:
        cc = _cc_from_catalog_item(item)
        if cc is not None:
            return EngineCcResolution(cc, False, source="catalog")

    approx = engine_capacity_cc_from_liters(liters)
    return EngineCcResolution(
        engine_cc=approx,
        approximate=approx is not None,
        source="liters" if approx is not None else None,
    )
