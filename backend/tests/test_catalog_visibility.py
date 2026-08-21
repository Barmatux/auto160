from types import SimpleNamespace

from app.catalog_ratings import _row_from_group
from app.catalog_visibility import listing_generation_allowed_for_model, listing_matches_generation


def test_row_from_group_marks_fully_hidden_generation():
    row = SimpleNamespace(
        make="Ford",
        model="Focus",
        generation="III",
        item_count=3,
        rated_count=0,
        rating_min=None,
        rating_max=None,
        year_from_min=2011,
        year_to_max=2014,
        first_item_id=42,
        hidden_count=3,
    )
    result = _row_from_group(row)
    assert result.hidden is True
    assert result.production_years == "2011 – 2014"
    assert result.photo_item_id == 42


def test_row_from_group_not_hidden_when_partially_visible():
    row = SimpleNamespace(
        make="Ford",
        model="Focus",
        generation="IV",
        item_count=3,
        rated_count=0,
        rating_min=None,
        rating_max=None,
        year_from_min=None,
        year_to_max=None,
        first_item_id=99,
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


def test_listing_generation_allowed_for_model():
    zafira_catalog = frozenset({"C", "C · Рестайлинг"})
    assert listing_generation_allowed_for_model(
        "B · Рестайлинг",
        catalog_generations=zafira_catalog,
        catalog_allows_unrated=False,
    ) is False
    assert listing_generation_allowed_for_model(
        "C · Рестайлинг",
        catalog_generations=zafira_catalog,
        catalog_allows_unrated=False,
    ) is True
    assert listing_generation_allowed_for_model(
        None,
        catalog_generations=zafira_catalog,
        catalog_allows_unrated=False,
    ) is False
    assert listing_generation_allowed_for_model(
        None,
        catalog_generations=frozenset(),
        catalog_allows_unrated=True,
    ) is True


def test_listing_generation_allowed_for_single_catalog_generation_without_listing_generation():
    assert listing_generation_allowed_for_model(
        None,
        catalog_generations=frozenset({"I"}),
        catalog_allows_unrated=False,
    ) is True
    assert listing_generation_allowed_for_model(
        None,
        catalog_generations=frozenset({"I", "I · Рестайлинг"}),
        catalog_allows_unrated=False,
    ) is False
