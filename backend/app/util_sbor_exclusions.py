"""Exclusions for cars that fail RF preferential recycling-fee (утильсбор) rules."""

from __future__ import annotations

import re
from typing import Any

from app.fuel_type_labels import FUEL_GROUP_DIESEL, classify_fuel_type

# Mercedes-Benz OM626/OM622 1.6 diesel 160 hp (118 kW) from 2016+ —
# does not qualify for preferential RF recycling fee.
MERCEDES_16_DIESEL_160_YEAR_FROM = 2016
MERCEDES_16_DIESEL_160_VOLUME_L = 1.6
MERCEDES_16_DIESEL_160_VOLUME_TOLERANCE = 0.05
MERCEDES_16_DIESEL_160_POWER_HP = 160

_MERCEDES_MAKE_KEYS = frozenset(
    {
        "mercedes",
        "mercedes benz",
        "mercedes-benz",
    }
)


def _normalize_make_key(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9]+", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def is_mercedes_make(value: str | None) -> bool:
    key = _normalize_make_key(value)
    if not key:
        return False
    if key in _MERCEDES_MAKE_KEYS:
        return True
    return key.startswith("mercedes")


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _volume_matches(volume_l: float | None) -> bool:
    if volume_l is None:
        return False
    return abs(float(volume_l) - MERCEDES_16_DIESEL_160_VOLUME_L) <= MERCEDES_16_DIESEL_160_VOLUME_TOLERANCE


def _is_diesel(*fuel_values: str | None) -> bool:
    for value in fuel_values:
        if classify_fuel_type(value) == FUEL_GROUP_DIESEL:
            return True
    return False


def is_mercedes_16_diesel_160_util_exclusion(
    *,
    make: str | None,
    fuel_type: str | None = None,
    engine_type: str | None = None,
    engine_volume_l: float | None = None,
    engine_capacity_l: float | None = None,
    engine_power_hp: int | None = None,
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    require_year_from_2016: bool = True,
) -> bool:
    """True when the car matches Mercedes 1.6 diesel 160 hp from 2016+ (утильсбор)."""
    if not is_mercedes_make(make):
        return False
    if not _is_diesel(fuel_type, engine_type):
        return False

    volume = _to_float(engine_volume_l)
    if volume is None:
        volume = _to_float(engine_capacity_l)
    if not _volume_matches(volume):
        return False

    power = _to_int(engine_power_hp)
    if power != MERCEDES_16_DIESEL_160_POWER_HP:
        return False

    if not require_year_from_2016:
        return True

    year_value = _to_int(year)
    if year_value is not None:
        return year_value >= MERCEDES_16_DIESEL_160_YEAR_FROM

    # Catalog modification year window: keep only pre-2016 ranges.
    year_to_value = _to_int(year_to)
    if year_to_value is not None and year_to_value < MERCEDES_16_DIESEL_160_YEAR_FROM:
        return False
    return True


def catalog_item_is_mercedes_16_diesel_160_util_exclusion(item: Any) -> bool:
    return is_mercedes_16_diesel_160_util_exclusion(
        make=getattr(item, "make", None),
        fuel_type=getattr(item, "fuel_type", None),
        engine_volume_l=getattr(item, "engine_volume_l", None),
        engine_power_hp=getattr(item, "engine_power_hp", None),
        year_from=getattr(item, "year_from", None),
        year_to=getattr(item, "year_to", None),
        require_year_from_2016=True,
    )


def listing_is_mercedes_16_diesel_160_util_exclusion(listing: Any) -> bool:
    return is_mercedes_16_diesel_160_util_exclusion(
        make=getattr(listing, "brand", None) or getattr(listing, "make", None),
        fuel_type=getattr(listing, "engine_type", None),
        engine_type=getattr(listing, "engine_type", None),
        engine_capacity_l=getattr(listing, "engine_capacity_l", None),
        engine_power_hp=getattr(listing, "engine_power_hp", None),
        year=getattr(listing, "year", None),
        require_year_from_2016=True,
    )


def catalog_payload_is_mercedes_16_diesel_160_util_exclusion(payload: dict[str, Any]) -> bool:
    return is_mercedes_16_diesel_160_util_exclusion(
        make=payload.get("make"),
        fuel_type=payload.get("fuel_type"),
        engine_volume_l=payload.get("engine_volume_l"),
        engine_power_hp=payload.get("engine_power_hp"),
        year_from=payload.get("year_from"),
        year_to=payload.get("year_to"),
        require_year_from_2016=True,
    )


def listing_payload_is_mercedes_16_diesel_160_util_exclusion(payload: dict[str, Any]) -> bool:
    return is_mercedes_16_diesel_160_util_exclusion(
        make=payload.get("brand") or payload.get("make"),
        fuel_type=payload.get("engine_type") or payload.get("fuel_type"),
        engine_type=payload.get("engine_type"),
        engine_capacity_l=payload.get("engine_capacity_l") or payload.get("engine_volume_l"),
        engine_power_hp=payload.get("engine_power_hp"),
        year=payload.get("year"),
        require_year_from_2016=True,
    )
