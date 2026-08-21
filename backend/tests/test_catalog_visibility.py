from types import SimpleNamespace

from app.catalog_ratings import _row_from_group


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
