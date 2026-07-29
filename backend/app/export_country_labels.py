"""Export country labels for catalog filters (av.by = Belarus only for now)."""

from __future__ import annotations

EXPORT_COUNTRY_BELARUS = "Беларусь"

# Filter dropdown options while catalog is sourced only from av.by.
EXPORT_COUNTRY_FILTER_OPTIONS: tuple[str, ...] = (EXPORT_COUNTRY_BELARUS,)

_BELARUS_ALIASES = frozenset({"беларусь", "belarus", "by"})


def is_belarus_export_country(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in _BELARUS_ALIASES or value.strip() == EXPORT_COUNTRY_BELARUS


def export_country_for_avby() -> str:
    return EXPORT_COUNTRY_BELARUS
