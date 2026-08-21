from datetime import date

from app.avby_price import extract_price_byn_from_advert, fix_rub_stored_as_byn
from app.exchange_rates import NbrbRates


def _sample_rates() -> NbrbRates:
    return NbrbRates(
        rate_date=date(2026, 8, 21),
        usd_rate=2.9829,
        usd_scale=1,
        rub_rate=3.5784,
        rub_scale=100,
    )


def test_extract_price_byn_prefers_amount_fiat():
    advert = {
        "price": {
            "byn": {"currency": "byn", "amount": 46533, "amountFiat": 46533.24},
            "rub": {"currency": "rub", "amount": 1300392},
            "usd": {"currency": "usd", "amount": 15600},
        }
    }
    assert extract_price_byn_from_advert(advert) == 46533.24


def test_extract_price_byn_uses_amount_when_fiat_missing():
    advert = {
        "price": {
            "byn": {"currency": "byn", "amount": 46533},
            "rub": {"currency": "rub", "amount": 1300392},
        }
    }
    assert extract_price_byn_from_advert(advert) == 46533


def test_extract_price_byn_ignores_other_currencies():
    advert = {
        "price": {
            "usd": {"currency": "usd", "amount": 15600},
            "rub": {"currency": "rub", "amount": 1300392},
        }
    }
    assert extract_price_byn_from_advert(advert) is None


def test_fix_rub_stored_as_byn_corrects_legacy_rows():
    rates = _sample_rates()
    corrected = fix_rub_stored_as_byn(1_325_934, rates)
    assert corrected is not None
    assert 45_000 <= corrected <= 48_000
    assert fix_rub_stored_as_byn(46_533, rates) == 46_533
