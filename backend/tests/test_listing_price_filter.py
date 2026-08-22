from datetime import date

from app.exchange_rates import NbrbRates
from app.listing_price_filter import (
    LISTING_PRICE_RANGE_OPTIONS,
    listing_price_range_byn_bounds,
    listing_price_range_options,
    parse_listing_price_range,
)


def _rates() -> NbrbRates:
    return NbrbRates(
        rate_date=date(2026, 8, 21),
        usd_rate=2.9829,
        usd_scale=1,
        rub_rate=3.5784,
        rub_scale=100,
    )


def test_parse_listing_price_range_accepts_known_slugs():
    assert parse_listing_price_range("1m_1_25m") == "1m_1_25m"
    assert parse_listing_price_range("unknown") is None
    assert parse_listing_price_range("") is None


def test_listing_price_range_options_match_requested_labels():
    labels = [option["label"] for option in listing_price_range_options()]
    assert labels == [
        "до 1 000 000 руб.",
        "1 000 000 - 1 250 000",
        "1 250 000 - 1 500 000",
        "1 500 000 - 2 000 000",
        "2 000 000 - 2 500 000",
        "2 500 000 - 3 000 000",
    ]


def test_listing_price_range_byn_bounds_for_rub_ranges():
    rates = _rates()
    up_to_1m = LISTING_PRICE_RANGE_OPTIONS[0]
    between_1m_and_125m = LISTING_PRICE_RANGE_OPTIONS[1]

    assert listing_price_range_byn_bounds(up_to_1m, rates) == (None, 35_784.0)
    assert listing_price_range_byn_bounds(between_1m_and_125m, rates) == (35_784.0, 44_730.0)

    low_price_byn = 3_000.0
    mid_price_byn = 40_000.0
    low_rub = rates.convert_byn_to_rub(low_price_byn)
    mid_rub = rates.convert_byn_to_rub(mid_price_byn)

    _, up_to_1m_max = listing_price_range_byn_bounds(up_to_1m, rates)
    min_1m_125m, max_1m_125m = listing_price_range_byn_bounds(between_1m_and_125m, rates)

    assert low_rub <= up_to_1m_max
    assert min_1m_125m < mid_rub <= max_1m_125m
