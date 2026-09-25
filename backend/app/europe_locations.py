"""Europe country location filter for /listings/eu."""

from __future__ import annotations

from sqlalchemy import or_

REGION_SLUG_LITHUANIA = "lt"
REGION_SLUG_ESTONIA = "ee"

EU_LOCATION_REGIONS: list[dict[str, str]] = [
    {"slug": REGION_SLUG_ESTONIA, "label": "Эстония"},
    {"slug": REGION_SLUG_LITHUANIA, "label": "Литва"},
]

_EU_REGION_LABEL_BY_SLUG = {item["slug"]: item["label"] for item in EU_LOCATION_REGIONS}

_EU_REGION_SOURCE: dict[str, str] = {
    REGION_SLUG_LITHUANIA: "autoplius",
    REGION_SLUG_ESTONIA: "auto24",
}

_EU_REGION_ALIASES: dict[str, str] = {
    "lt": REGION_SLUG_LITHUANIA,
    "lithuania": REGION_SLUG_LITHUANIA,
    "litva": REGION_SLUG_LITHUANIA,
    "литва": REGION_SLUG_LITHUANIA,
    "ee": REGION_SLUG_ESTONIA,
    "estonia": REGION_SLUG_ESTONIA,
    "eesti": REGION_SLUG_ESTONIA,
    "эстония": REGION_SLUG_ESTONIA,
}


def normalize_europe_region_slug(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    return _EU_REGION_ALIASES.get(raw.casefold())


def parse_europe_location_filter_values(
    raw_regions: list[str] | None,
    raw_cities: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    regions: list[str] = []
    for raw in raw_regions or []:
        slug = normalize_europe_region_slug(raw)
        if slug and slug not in regions:
            regions.append(slug)
    # Accept country labels submitted as city=Литва / city=Эстония too.
    for raw in raw_cities or []:
        slug = normalize_europe_region_slug(raw)
        if slug and slug not in regions:
            regions.append(slug)
    return regions, []


def europe_location_filter_groups() -> list[dict]:
    return [
        {
            "type": "region",
            "slug": region["slug"],
            "label": region["label"],
            "cities": [],
        }
        for region in EU_LOCATION_REGIONS
    ]


def europe_location_filter_checked_state(region_slugs: list[str]) -> dict[str, set[str] | bool]:
    return {
        "standalone": False,
        "regions": set(region_slugs),
        "cities": set(),
    }


def europe_location_filter_display_label(region_slugs: list[str]) -> str:
    labels = [
        _EU_REGION_LABEL_BY_SLUG[slug]
        for slug in region_slugs
        if slug in _EU_REGION_LABEL_BY_SLUG
    ]
    if not labels:
        return "Любой"
    if len(labels) == 1:
        return labels[0]
    return f"Выбрано пунктов: {len(labels)}"


def europe_location_sources(region_slugs: list[str]) -> list[str]:
    sources: list[str] = []
    for slug in region_slugs:
        source = _EU_REGION_SOURCE.get(slug)
        if source and source not in sources:
            sources.append(source)
    return sources


def apply_europe_location_filter(query, source_column, *, region_slugs: list[str]):
    sources = europe_location_sources(region_slugs)
    if not sources:
        return query
    if len(sources) == 1:
        return query.filter(source_column == sources[0])
    return query.filter(or_(*(source_column == source for source in sources)))
