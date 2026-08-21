"""Tests for Belarus location filter helpers."""

from app.belarus_locations import (
    MINSK_CITY,
    REGION_SLUG_BREST,
    REGION_SLUG_GOMEL,
    expand_location_filter_to_city_names,
    location_filter_checked_state,
    location_filter_display_label,
    location_filter_groups,
    normalize_region_slug,
    parse_location_filter_values,
)


def test_normalize_region_slug():
    assert normalize_region_slug("brest") == REGION_SLUG_BREST
    assert normalize_region_slug("Брестская область") == REGION_SLUG_BREST
    assert normalize_region_slug("unknown") is None


def test_parse_location_filter_values():
    regions, cities = parse_location_filter_values(["brest", "brest"], ["Минск", "Брест", ""])
    assert regions == [REGION_SLUG_BREST]
    assert cities == [MINSK_CITY, "Брест"]


def test_expand_location_filter_to_city_names():
    available = {"Минск", "Брест", "Пинск", "Гомель"}
    expanded = expand_location_filter_to_city_names(
        [REGION_SLUG_BREST],
        [MINSK_CITY],
        available_cities=available,
    )
    assert expanded == ["Брест", "Минск", "Пинск"]

    only_cities = expand_location_filter_to_city_names(
        [],
        ["Гомель", "Пинск"],
        available_cities=available,
    )
    assert only_cities == ["Гомель", "Пинск"]


def test_location_filter_checked_state():
    checked = location_filter_checked_state([REGION_SLUG_BREST], ["Брест"])
    assert checked["standalone"] is False
    assert REGION_SLUG_BREST in checked["regions"]
    assert "Брест" in checked["cities"]
    assert "Пинск" in checked["cities"]

    partial = location_filter_checked_state([], ["Брест", MINSK_CITY])
    assert partial["standalone"] is True
    assert partial["regions"] == set()
    assert partial["cities"] == {"Брест"}


def test_location_filter_display_label():
    assert location_filter_display_label([], []) == "Любой"
    assert location_filter_display_label([], [MINSK_CITY]) == MINSK_CITY
    assert location_filter_display_label([REGION_SLUG_BREST], []) == "Брестская область"
    assert (
        location_filter_display_label([REGION_SLUG_BREST], ["Гомель"])
        == "Выбрано пунктов: 2"
    )


def test_location_filter_groups_order():
    groups = location_filter_groups(["Минск", "Брест", "Гомель", "Борисов"])
    assert groups[0]["type"] == "standalone"
    assert groups[0]["label"] == MINSK_CITY
    region_labels = [group["label"] for group in groups if group["type"] == "region"]
    assert region_labels == [
        "Брестская область",
        "Витебская область",
        "Гомельская область",
        "Гродненская область",
        "Минская область",
        "Могилёвская область",
    ]
    brest_group = next(group for group in groups if group.get("slug") == REGION_SLUG_BREST)
    assert [city["slug"] for city in brest_group["cities"]] == ["Брест"]
    minsk_region = next(group for group in groups if group.get("slug") == "minsk-region")
    assert [city["slug"] for city in minsk_region["cities"]] == ["Борисов"]
