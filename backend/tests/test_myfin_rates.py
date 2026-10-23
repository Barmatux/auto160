from app.myfin_rates import _parse_rates


SAMPLE_HTML = """
<html><body>
Колебания курса USD </span></div><div>2.946 β</div><div>2.947 β</div>
Колебания курса EUR </span></div><div>3.304 β</div><div>3.304 β</div>
Колебания курса RUB </span></div><div>3.4767 β</div><div>3.61 β</div>
</body></html>
"""


def test_parse_myfin_best_buy_rates():
    rates = _parse_rates(SAMPLE_HTML)
    assert rates is not None
    assert rates.usd_buy == 2.946
    assert rates.eur_buy == 3.304
    assert rates.rub100_buy == 3.4767
    assert rates.format_usd() == "2,946"
    assert rates.format_rub100() == "3,4767"
