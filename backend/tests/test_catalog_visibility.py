from types import SimpleNamespace

from app.catalog_ratings import _row_from_group
from app.catalog_visibility import listing_matches_generation


def test_row_from_group_marks_fully_hidden_generation():
    row = SimpleNamespace(
        make="Ford",
        model="Focus",
        generation="III",
        item_count=3,
        rated_count=0,
        rating_min=None,
        rating_max=None,
        hidden_count=3,
    )
    result = _row_from_group(row)
    assert result.hidden is True


def test_row_from_group_not_hidden_when_partially_visible():
    row = SimpleNamespace(
        make="Ford",
        model="Focus",
        generation="IV",
        item_count=3,
        rated_count=0,
        rating_min=None,
        rating_max=None,
        hidden_count=1,
    )
    result = _row_from_group(row)
    assert result.hidden is False


def test_listing_matches_generation_by_exact_and_suffix():
    assert listing_matches_generation("III", "III") is True
    assert listing_matches_generation("Focus III (2011-2014)", "III") is True
    assert listing_matches_generation("IV", "III") is False
    assert listing_matches_generation(None, "") is True
    assert listing_matches_generation("III", "") is False
