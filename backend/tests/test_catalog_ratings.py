from decimal import Decimal

from app.catalog_ratings import (
    RATING_FILTER_UNRATED,
    format_production_years,
    format_rating,
    generation_key,
    generation_label,
    parse_rating,
    parse_rating_filter_values,
    rating_filter_tokens,
)


def test_format_production_years():
    assert format_production_years(None, None) == "—"
    assert format_production_years(2019, 2024) == "2019 – 2024"
    assert format_production_years(2019, None) == "2019 – ?"


def test_generation_key_and_label():
    assert generation_key(None) == ""
    assert generation_key("  II  ") == "II"
    assert generation_label(None) == "Без поколения"
    assert generation_label("") == "Без поколения"
    assert generation_label("II") == "II"


def test_format_rating_int_and_decimal():
    assert format_rating(None) == ""
    assert format_rating(1) == "1"
    assert format_rating(1.0) == "1"
    assert format_rating(Decimal("2.00")) == "2"
    assert format_rating(8.5) == "8.5"


def test_parse_rating_accepts_blank_and_numbers():
    assert parse_rating(None) is None
    assert parse_rating("") is None
    assert parse_rating("  ") is None
    assert parse_rating("1") == 1.0
    assert parse_rating("8,5") == 8.5
    assert parse_rating(3) == 3.0


def test_parse_rating_rejects_out_of_range():
    for raw in (0, 100, "nope"):
        try:
            parse_rating(raw)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {raw!r}")


def test_parse_rating_filter_values():
    ratings, include_unrated = parse_rating_filter_values([])
    assert ratings == frozenset()
    assert include_unrated is False

    ratings, include_unrated = parse_rating_filter_values(["1", "2", RATING_FILTER_UNRATED])
    assert ratings == frozenset({1, 2})
    assert include_unrated is True

    ratings, include_unrated = parse_rating_filter_values(["9", "bad", ""])
    assert ratings == frozenset()
    assert include_unrated is False


def test_rating_filter_tokens():
    assert rating_filter_tokens(frozenset({3, 1}), include_unrated=False) == ["1", "3"]
    assert rating_filter_tokens(frozenset({2}), include_unrated=True) == ["2", RATING_FILTER_UNRATED]
