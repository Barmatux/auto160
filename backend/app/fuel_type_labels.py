"""Normalize fuel type labels for catalog and listing filters."""

from __future__ import annotations

FUEL_GROUP_DIESEL = "дизель"
FUEL_GROUP_PETROL = "бензин"
FUEL_GROUP_GAS_PETROL = "Газ-бензин"
FUEL_GROUP_HYBRID = "Гибрид"
FUEL_GROUP_ELECTRIC = "Электро"

FUEL_FILTER_ORDER = (
    FUEL_GROUP_PETROL,
    FUEL_GROUP_DIESEL,
    FUEL_GROUP_GAS_PETROL,
    FUEL_GROUP_HYBRID,
    FUEL_GROUP_ELECTRIC,
)

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

ELECTRIC_EXACT_KEYS = frozenset(
    {
        "электро",
        "электричество",
        "electric",
        "ev",
    }
)

HYBRID_MARKERS = ("гибрид", "hybrid", "phev", "mhev")


def normalize_fuel_type_key(value: str) -> str:
    cleaned = value.strip().lower().replace("ё", "е").replace("\xa0", " ")
    return " ".join(cleaned.split())


def classify_fuel_type(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None

    key = normalize_fuel_type_key(trimmed)

    if any(marker in key for marker in HYBRID_MARKERS):
        return FUEL_GROUP_HYBRID

    if "газ" in key:
        return FUEL_GROUP_GAS_PETROL

    if key in DIESEL_EXACT_KEYS or key.startswith("дизель"):
        return FUEL_GROUP_DIESEL

    if key in PETROL_EXACT_KEYS:
        return FUEL_GROUP_PETROL

    if key.startswith("аи"):
        return FUEL_GROUP_PETROL

    if key in ELECTRIC_EXACT_KEYS or key.startswith("электро"):
        return FUEL_GROUP_ELECTRIC

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
