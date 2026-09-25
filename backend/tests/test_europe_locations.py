"""Tests for Europe location filter helpers."""

from app.europe_locations import (
    REGION_SLUG_ESTONIA,
    REGION_SLUG_LITHUANIA,
    europe_location_filter_checked_state,
    europe_location_filter_display_label,
    europe_location_filter_groups,
    europe_location_sources,
    normalize_europe_region_slug,
    parse_europe_location_filter_values,
)


def test_normalize_europe_region_slug():
    assert normalize_europe_region_slug("ee") == REGION_SLUG_ESTONIA
    assert normalize_europe_region_slug("Эстония") == REGION_SLUG_ESTONIA
    assert normalize_europe_region_slug("lt") == REGION_SLUG_LITHUANIA
    assert normalize_europe_region_slug("Литва") == REGION_SLUG_LITHUANIA
    assert normalize_europe_region_slug("brest") is None


def test_parse_europe_location_filter_values():
    regions, cities = parse_europe_location_filter_values(["ee", "lt", "ee"], ["Литва", ""])
    assert regions == [REGION_SLUG_ESTONIA, REGION_SLUG_LITHUANIA]
    assert cities == []


def test_europe_location_filter_groups_order():
    groups = europe_location_filter_groups()
    assert [group["label"] for group in groups] == ["Эстония", "Литва"]
    assert all(group["type"] == "region" for group in groups)
    assert all(group["cities"] == [] for group in groups)


def test_europe_location_filter_display_and_sources():
    assert europe_location_filter_display_label([]) == "Любой"
    assert europe_location_filter_display_label([REGION_SLUG_ESTONIA]) == "Эстония"
    assert europe_location_filter_display_label(
        [REGION_SLUG_ESTONIA, REGION_SLUG_LITHUANIA]
    ) == "Выбрано пунктов: 2"
    assert europe_location_sources([REGION_SLUG_ESTONIA]) == ["auto24"]
    assert europe_location_sources([REGION_SLUG_LITHUANIA, REGION_SLUG_ESTONIA]) == [
        "autoplius",
        "auto24",
    ]
    checked = europe_location_filter_checked_state([REGION_SLUG_LITHUANIA])
    assert checked["standalone"] is False
    assert REGION_SLUG_LITHUANIA in checked["regions"]
