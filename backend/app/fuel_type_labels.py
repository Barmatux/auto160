"""Normalize fuel type labels for catalog filters."""

from __future__ import annotations

FUEL_GROUP_DIESEL = "дизель"
FUEL_GROUP_PETROL = "бензин"
FUEL_GROUP_GAS_PETROL = "Газ-бензин"

FUEL_FILTER_ORDER = (FUEL_GROUP_PETROL, FUEL_GROUP_DIESEL, FUEL_GROUP_GAS_PETROL)

DIESEL_EXACT_KEYS = frozenset(
    {
        "diesel",
        "дизель",
        "дизельное топливо",
        "дт",
        "dt",
    }
)

PETROL_EXACT_KEYS = frozenset(
    {
        "petrol",
        "gasoline",
        "бензин",
        "этанол",
        "ethanol",
    }
)


def normalize_fuel_type_key(value: str) -> str:
    return value.strip().lower().replace("ё", "е")


def classify_fuel_type(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None

    key = normalize_fuel_type_key(trimmed)

    if "газ" in key:
        return FUEL_GROUP_GAS_PETROL

    if key in DIESEL_EXACT_KEYS or key.startswith("дизель"):
        return FUEL_GROUP_DIESEL

    if key in PETROL_EXACT_KEYS:
        return FUEL_GROUP_PETROL

    if key.startswith("аи"):
        return FUEL_GROUP_PETROL

    return trimmed[0].upper() + trimmed[1:] if trimmed else trimmed


def normalize_fuel_type_label(value: str | None) -> str | None:
    return classify_fuel_type(value)


def fuel_type_filter_options(raw_values: list[str]) -> list[str]:
    labels = {classify_fuel_type(value) for value in raw_values if value}
    labels.discard(None)
    grouped = [label for label in FUEL_FILTER_ORDER if label in labels]
    other = sorted(label for label in labels if label not in FUEL_FILTER_ORDER)
    return grouped + other


def fuel_type_db_values_for_filter(raw_values: list[str], canonical: str | None) -> list[str]:
    if not canonical:
        return []
    target = classify_fuel_type(canonical)
    if not target:
        return []
    matched = [value for value in raw_values if classify_fuel_type(value) == target]
    return matched or [canonical]
