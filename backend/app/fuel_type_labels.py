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

# Higher rank wins when av.by stores octane (АИ-95) separately from engine type.
_FUEL_GROUP_RANK = {
    FUEL_GROUP_HYBRID: 50,
    FUEL_GROUP_ELECTRIC: 50,
    FUEL_GROUP_GAS_PETROL: 30,
    FUEL_GROUP_DIESEL: 20,
    FUEL_GROUP_PETROL: 10,
}


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


def _label_from_spec_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("label", "name", "title"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
        return None
    text = str(value).strip()
    return text or None


def fuel_labels_from_raw_specs(raw_specs: dict | None) -> list[str]:
    """Collect engine/fuel labels from av.by catalog JSON.

    `modification.engineType` is the real group (e.g. бензин (гибрид));
    `modification_detail.fuel` is often just octane (АИ-95).
    """
    if not isinstance(raw_specs, dict):
        return []
    labels: list[str] = []
    seen: set[str] = set()

    def add(value: object) -> None:
        label = _label_from_spec_value(value)
        if label and label not in seen:
            seen.add(label)
            labels.append(label)

    modification = raw_specs.get("modification")
    if isinstance(modification, dict):
        add(modification.get("engineType"))
    detail = raw_specs.get("modification_detail")
    if isinstance(detail, dict):
        add(detail.get("engineType"))
        add(detail.get("fuel"))
    return labels


def preferred_fuel_type(*values: str | None) -> str | None:
    """Pick the most specific fuel/engine label among candidates."""
    best: str | None = None
    best_rank = -1
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        group = classify_fuel_type(text)
        rank = _FUEL_GROUP_RANK.get(group, 0) if group else 0
        if rank > best_rank:
            best = text
            best_rank = rank
    return best


def resolved_catalog_fuel_type(fuel_type: str | None, raw_specs: dict | None) -> str | None:
    """Effective catalog fuel type: prefer engineType over octane-only fuel."""
    return preferred_fuel_type(fuel_type, *fuel_labels_from_raw_specs(raw_specs))
