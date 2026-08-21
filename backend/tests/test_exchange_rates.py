from datetime import date

from app.exchange_rates import NbrbRates
from app.listing_display import build_listing_price_display


def test_nbrb_rates_convert_byn_to_foreign_currencies():
    rates = NbrbRates(
        rate_date=date(2026, 8, 21),
        usd_rate=2.9829,
        usd_scale=1,
        rub_rate=3.5784,
        rub_scale=100,
    )
    assert round(rates.convert_byn_to_usd(29_829)) == 10_000
    assert round(rates.convert_byn_to_rub(3_578.4)) == 100_000


def test_build_listing_price_display_includes_reference_disclaimer():
    rates = NbrbRates(
        rate_date=date(2026, 8, 21),
        usd_rate=2.9829,
        usd_scale=1,
        rub_rate=3.5784,
        rub_scale=100,
    )
    display = build_listing_price_display(29_829, rates)
    assert display.byn_formatted == "29 829"
    assert display.rub_formatted == "833 600"
    assert display.usd_formatted == "$10 000"
    assert display.has_conversions is True
    assert "НБ РБ" in (display.disclaimer or "")
    assert "21.08.2026" in (display.disclaimer or "")
