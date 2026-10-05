from datetime import date
from types import SimpleNamespace

from app.exchange_rates import NbrbRates
from app.listing_display import (
    build_europe_listing_price_display,
    build_listing_price_display,
    listing_price_display,
)


def test_nbrb_rates_convert_byn_to_foreign_currencies():
    rates = NbrbRates(
        rate_date=date(2026, 8, 21),
        usd_rate=2.9829,
        usd_scale=1,
        rub_rate=3.5784,
        rub_scale=100,
        eur_rate=3.5,
        eur_scale=1,
    )
    assert round(rates.convert_byn_to_usd(29_829)) == 10_000
    assert round(rates.convert_byn_to_rub(3_578.4)) == 100_000
    assert round(rates.convert_rub_to_byn(100_000)) == 3_578
    assert round(rates.convert_byn_to_eur(35_000)) == 10_000


def test_build_listing_price_display_includes_reference_disclaimer():
    rates = NbrbRates(
        rate_date=date(2026, 8, 21),
        usd_rate=2.9829,
        usd_scale=1,
        rub_rate=3.5784,
        rub_scale=100,
        eur_rate=3.5,
        eur_scale=1,
    )
    display = build_listing_price_display(29_829, rates)
    assert display.byn_formatted == "29 829"
    assert display.rub_formatted == "833 600"
    assert display.usd_formatted == "$10 000"
    assert display.eur_formatted is None
    assert display.has_conversions is True
    assert display.is_europe is False
    assert "ориентировоч" in (display.disclaimer or "").lower()
    assert "НБ РБ" in (display.disclaimer or "")
    assert "21.08.2026" in (display.disclaimer or "")


def test_europe_listing_price_display_shows_eur_and_rub():
    rates = NbrbRates(
        rate_date=date(2026, 8, 21),
        usd_rate=2.9829,
        usd_scale=1,
        rub_rate=3.5784,
        rub_scale=100,
        eur_rate=3.5,
        eur_scale=1,
    )
    display = build_europe_listing_price_display(35_000, rates)
    assert display.is_europe is True
    assert display.label_prefix == "Цена в 🇪🇺"
    assert display.eur_formatted == "10 000"
    assert display.rub_formatted == "978 091"
    assert display.usd_formatted is None
    assert display.has_conversions is True
    assert "евро" in (display.disclaimer or "").lower()


def test_listing_price_display_filter_routes_europe_sources():
    assert listing_price_display(SimpleNamespace(price=1000, source="auto24")).is_europe is True
    assert listing_price_display(SimpleNamespace(price=1000, source="autoplius")).is_europe is True
    assert listing_price_display(SimpleNamespace(price=1000, source="av.by")).is_europe is False
    assert listing_price_display(1000).is_europe is False
