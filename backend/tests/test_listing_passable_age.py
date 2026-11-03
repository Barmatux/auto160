from datetime import date
from types import SimpleNamespace

from app.listing_passable_age import (
    PASSABLE_AGE_MAX_MONTHS,
    PASSABLE_AGE_MIN_MONTHS,
    listing_matches_passable_age,
    passable_registration_window,
)


def test_passable_window_is_2y8m_to_4y10m():
    today = date(2026, 10, 29)
    start, end = passable_registration_window(today=today)
    assert start == date(2021, 12, 29)
    assert end == date(2024, 2, 29)
    assert PASSABLE_AGE_MIN_MONTHS == 32
    assert PASSABLE_AGE_MAX_MONTHS == 58


def test_matches_with_registration_month():
    today = date(2026, 10, 29)
    # Inside window
    assert listing_matches_passable_age(
        SimpleNamespace(title="Toyota Yaris 2023-05 m.", year=2023),
        today=today,
    )
    # Too new (< 2y8m)
    assert not listing_matches_passable_age(
        SimpleNamespace(title="Toyota Yaris 2024-06 m.", year=2024),
        today=today,
    )
    # Too old (> 4y10m)
    assert not listing_matches_passable_age(
        SimpleNamespace(title="Toyota Yaris 2021-11 m.", year=2021),
        today=today,
    )


def test_year_only_overlaps_window():
    today = date(2026, 10, 29)
    assert listing_matches_passable_age(SimpleNamespace(title="Toyota Yaris", year=2023), today=today)
    assert listing_matches_passable_age(SimpleNamespace(title="Toyota Yaris", year=2021), today=today)
    assert listing_matches_passable_age(SimpleNamespace(title="Toyota Yaris", year=2024), today=today)
    assert not listing_matches_passable_age(SimpleNamespace(title="Toyota Yaris", year=2020), today=today)
    assert not listing_matches_passable_age(SimpleNamespace(title="Toyota Yaris", year=2025), today=today)
