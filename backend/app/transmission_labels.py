"""Normalize catalog transmission values and grouped filter slugs."""

from __future__ import annotations

from sqlalchemy import or_

TRANSMISSION_SLUG_MANUAL = "manual"
TRANSMISSION_SLUG_AUTO = "auto"
TRANSMISSION_SLUG_AUTO_CLASSIC = "auto-classic"
TRANSMISSION_SLUG_ROBOT = "robot"
TRANSMISSION_SLUG_CVT = "cvt"

TRANSMISSION_AUTO_SLUGS = (
    TRANSMISSION_SLUG_AUTO_CLASSIC,
    TRANSMISSION_SLUG_ROBOT,
    TRANSMISSION_SLUG_CVT,
)

TRANSMISSION_FILTER_GROUPS: list[dict] = [
    {
        "slug": TRANSMISSION_SLUG_AUTO,
        "label": "автомат",
        "subtypes": [
            {"slug": TRANSMISSION_SLUG_AUTO_CLASSIC, "label": "автоматическая"},
            {"slug": TRANSMISSION_SLUG_ROBOT, "label": "робот"},
            {"slug": TRANSMISSION_SLUG_CVT, "label": "вариатор"},
        ],
    },
    {
        "slug": TRANSMISSION_SLUG_MANUAL,
        "label": "механика",
        "subtypes": [],
    },
]

_FILTER_SLUG_ALIASES: dict[str, str] = {
    "auto": TRANSMISSION_SLUG_AUTO,
    "автомат": TRANSMISSION_SLUG_AUTO_CLASSIC,
    "automatic": TRANSMISSION_SLUG_AUTO_CLASSIC,
    "автоматическая": TRANSMISSION_SLUG_AUTO_CLASSIC,
    "auto-classic": TRANSMISSION_SLUG_AUTO_CLASSIC,
    "robot": TRANSMISSION_SLUG_ROBOT,
    "dct": TRANSMISSION_SLUG_ROBOT,
    "робот": TRANSMISSION_SLUG_ROBOT,
    "cvt": TRANSMISSION_SLUG_CVT,
    "вариатор": TRANSMISSION_SLUG_CVT,
    "manual": TRANSMISSION_SLUG_MANUAL,
    "механика": TRANSMISSION_SLUG_MANUAL,
    "механ": TRANSMISSION_SLUG_MANUAL,
}


def normalize_transmission_key(value: str) -> str:
    cleaned = value.strip().lower().replace("ё", "е").replace("\xa0", " ")
    return " ".join(cleaned.split())


def normalize_transmission_filter_slug(value: str | None) -> str | None:
    if value is None:
        return None
    key = normalize_transmission_key(value)
    if not key:
        return None
    return _FILTER_SLUG_ALIASES.get(key)


def parse_transmission_filter_values(raw_values: list[str] | None) -> list[str]:
    if not raw_values:
        return []
    slugs: list[str] = []
    for raw in raw_values:
        slug = normalize_transmission_filter_slug(raw)
        if slug and slug not in slugs:
            slugs.append(slug)
    return slugs


def expand_transmission_filter_slugs(slugs: list[str]) -> list[str]:
    expanded: list[str] = []
    for slug in slugs:
        if slug == TRANSMISSION_SLUG_AUTO:
            for child in TRANSMISSION_AUTO_SLUGS:
                if child not in expanded:
                    expanded.append(child)
            continue
        if slug not in expanded:
            expanded.append(slug)
    return expanded


def classify_transmission_slug(value: str | None) -> str | None:
    if value is None:
        return None
    key = normalize_transmission_key(value)
    if not key:
        return None

    if key in {"manual", "механика"} or key.startswith("механ"):
        return TRANSMISSION_SLUG_MANUAL
    if key in {"cvt", "вариатор"} or "вариатор" in key:
        return TRANSMISSION_SLUG_CVT
    if key in {"dct", "robot", "робот"} or key.startswith("робот"):
        return TRANSMISSION_SLUG_ROBOT
    if key in {"automatic", "автомат", "автоматическая"} or "автомат" in key:
        return TRANSMISSION_SLUG_AUTO_CLASSIC
    return None


def transmission_db_values_for_slug(raw_values: list[str], slug: str) -> list[str]:
    matched = [value for value in raw_values if classify_transmission_slug(value) == slug]
    return matched


def transmission_db_values_for_slugs(raw_values: list[str], slugs: list[str]) -> list[str]:
    expanded = expand_transmission_filter_slugs(slugs)
    matched: list[str] = []
    for slug in expanded:
        for value in transmission_db_values_for_slug(raw_values, slug):
            if value not in matched:
                matched.append(value)
    return matched


def transmission_filter_checked_slugs(slugs: list[str]) -> set[str]:
    checked = set(slugs)
    if TRANSMISSION_SLUG_AUTO in checked:
        checked.update(TRANSMISSION_AUTO_SLUGS)
        return checked
    if all(slug in checked for slug in TRANSMISSION_AUTO_SLUGS):
        checked.add(TRANSMISSION_SLUG_AUTO)
    return checked


def transmission_filter_display_label(slugs: list[str]) -> str:
    if not slugs:
        return "Любая"
    labels: list[str] = []
    slugs_set = set(slugs)
    auto_all = TRANSMISSION_SLUG_AUTO in slugs_set or all(
        slug in slugs_set for slug in TRANSMISSION_AUTO_SLUGS
    )
    if auto_all:
        labels.append("автомат")
    else:
        subtype_labels = {
            subtype["slug"]: subtype["label"]
            for group in TRANSMISSION_FILTER_GROUPS
            for subtype in group.get("subtypes", [])
        }
        for slug in TRANSMISSION_AUTO_SLUGS:
            if slug in slugs_set:
                labels.append(subtype_labels[slug])
    if TRANSMISSION_SLUG_MANUAL in slugs_set:
        labels.append("механика")
    return ", ".join(labels) if labels else "Любая"


def transmission_filter_submit_slugs(slugs: list[str]) -> list[str]:
    checked = transmission_filter_checked_slugs(slugs)
    submitted: list[str] = []
    if TRANSMISSION_SLUG_AUTO in checked:
        submitted.append(TRANSMISSION_SLUG_AUTO)
    else:
        for slug in TRANSMISSION_AUTO_SLUGS:
            if slug in checked and slug not in submitted:
                submitted.append(slug)
    if TRANSMISSION_SLUG_MANUAL in checked and TRANSMISSION_SLUG_MANUAL not in submitted:
        submitted.append(TRANSMISSION_SLUG_MANUAL)
    return submitted


def apply_catalog_transmission_filter(query, column, *, raw_values: list[str], slugs: list[str]):
    if not slugs:
        return query
    match_values = transmission_db_values_for_slugs(raw_values, slugs)
    if match_values:
        return query.filter(column.in_(match_values))
    predicates = []
    for slug in expand_transmission_filter_slugs(slugs):
        if slug == TRANSMISSION_SLUG_MANUAL:
            predicates.extend(
                [
                    column.ilike("manual"),
                    column.ilike("механика"),
                    column.ilike("механ%"),
                ]
            )
        elif slug == TRANSMISSION_SLUG_AUTO_CLASSIC:
            predicates.extend(
                [
                    column.ilike("automatic"),
                    column.ilike("автомат"),
                    column.ilike("автоматическая"),
                ]
            )
        elif slug == TRANSMISSION_SLUG_ROBOT:
            predicates.extend(
                [
                    column.ilike("dct"),
                    column.ilike("robot"),
                    column.ilike("робот"),
                ]
            )
        elif slug == TRANSMISSION_SLUG_CVT:
            predicates.extend(
                [
                    column.ilike("cvt"),
                    column.ilike("вариатор"),
                ]
            )
    if not predicates:
        return query
    return query.filter(or_(*predicates))
