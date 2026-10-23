from app.myfin_rates import _parse_rates


SAMPLE_HTML = """
<html><body>
Колебания курса USD </span></div><div>2.946 β</div><div>2.947 β</div>
Колебания курса EUR </span></div><div>3.304 β</div><div>3.304 β</div>
Колебания курса RUB </span></div><div>3.4767 β</div><div>3.61 β</div>
</body></html>
"""


def test_parse_myfin_rates_quoted_in_rub():
    rates = _parse_rates(SAMPLE_HTML)
    assert rates is not None
    assert rates.usd_buy_byn == 2.946
    assert rates.eur_buy_byn == 3.304
    assert rates.rub100_buy_byn == 3.4767
    # Cross to RUB: usd_byn * 100 / rub100_byn
    assert abs(rates.usd_rub - (2.946 * 100 / 3.4767)) < 1e-6
    assert abs(rates.eur_rub - (3.304 * 100 / 3.4767)) < 1e-6
    assert abs(rates.byn_rub - (100 / 3.4767)) < 1e-6
    assert "₽" not in rates.format_usd_rub()
    assert "," in rates.format_usd_rub() or rates.format_usd_rub().replace(".", "").isdigit()
