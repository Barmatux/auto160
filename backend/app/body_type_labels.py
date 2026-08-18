"""Normalize body type labels for filters and display."""

from __future__ import annotations

from sqlalchemy import and_, or_

# Keys are lowercased, trimmed; values are canonical Russian labels (capitalized).
BODY_TYPE_ALIASES: dict[str, str] = {
    "sedan": "Седан",
    "седан": "Седан",
    "hatchback": "Хэтчбек 5 дв.",
    "хэтчбек": "Хэтчбек 5 дв.",
    "хэтчбек 3 дв.": "Хэтчбек 3 дв.",
    "хэтчбек 5 дв.": "Хэтчбек 5 дв.",
    "wagon": "Универсал",
    "estate": "Универсал",
    "универсал": "Универсал",
    "minivan": "Минивэн",
    "минивэн": "Минивэн",
    "crossover": "Кроссовер",
    "кроссовер": "Кроссовер",
    "suv": "Внедорожник 5 дв.",
    "внедорожник 5 дв.": "Внедорожник 5 дв.",
    "coupe": "Купе",
    "купе": "Купе",
    "cabrio": "Кабриолет",
    "convertible": "Кабриолет",
    "кабриолет": "Кабриолет",
    "pickup": "Пикап",
    "пикап": "Пикап",
    "van": "Легковой фургон",
    "легковой фургон": "Легковой фургон",
    "liftback": "Лифтбек",
    "лифтбек": "Лифтбек",
    "микроавтобус грузопассажирский": "Микроавтобус грузопассажирский",
    "микроавтобус пассажирский": "Микроавтобус пассажирский",
}

# Commercial / cargo types that are out of scope for Auto160.
HIDDEN_BODY_TYPE_LABELS = frozenset({"Пикап"})
HIDDEN_BODY_TYPE_MARKERS = ("пикап", "pickup")


def normalize_body_type_key(value: str) -> str:
    return value.strip().lower().replace("ё", "е")


def capitalize_label(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return trimmed
    return trimmed[0].upper() + trimmed[1:]


def normalize_body_type_label(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    canonical = BODY_TYPE_ALIASES.get(normalize_body_type_key(trimmed))
    if canonical:
        return canonical
    return capitalize_label(trimmed)


def is_hidden_body_type(value: str | None) -> bool:
    label = normalize_body_type_label(value)
    if label in HIDDEN_BODY_TYPE_LABELS:
        return True
    if not value:
        return False
    key = normalize_body_type_key(value)
    return any(marker in key for marker in HIDDEN_BODY_TYPE_MARKERS)


def exclude_hidden_body_type(query, column):
    """Drop pickup/cargo rows from catalog and listing queries."""
    return query.filter(
        or_(
            column.is_(None),
            and_(*[~column.ilike(f"%{marker}%") for marker in HIDDEN_BODY_TYPE_MARKERS]),
        )
    )


def body_type_filter_options(raw_values: list[str]) -> list[str]:
    labels = {normalize_body_type_label(value) for value in raw_values if value}
    labels.discard(None)
    labels -= HIDDEN_BODY_TYPE_LABELS
    return sorted(label for label in labels if label)


def body_type_db_values_for_filter(raw_values: list[str], canonical: str | None) -> list[str]:
    if not canonical:
        return []
    target = normalize_body_type_label(canonical)
    if not target:
        return []
    matched = [value for value in raw_values if normalize_body_type_label(value) == target]
    return matched or [canonical]
