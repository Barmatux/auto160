"""Normalize body type labels for filters and display."""

from __future__ import annotations

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


def body_type_filter_options(raw_values: list[str]) -> list[str]:
    labels = {normalize_body_type_label(value) for value in raw_values if value}
    labels.discard(None)
    return sorted(label for label in labels if label)


def body_type_db_values_for_filter(raw_values: list[str], canonical: str | None) -> list[str]:
    if not canonical:
        return []
    target = normalize_body_type_label(canonical)
    if not target:
        return []
    matched = [value for value in raw_values if normalize_body_type_label(value) == target]
    return matched or [canonical]
