from app.bca_admin import corrected_mileage, country_label, fuel_label, media_download_url, public_lot_url_ok


def test_corrected_mileage_drops_trailing_decimal_zero():
    assert corrected_mileage(1463080) == 146308
    assert corrected_mileage(25812) == 25812
    assert corrected_mileage(None) is None


def test_country_and_fuel_labels():
    assert country_label("DE") == "Германия (DE)"
    assert fuel_label("BEV - battery electric vehicle  100% electric") == "Электро"
    assert fuel_label("Diesel") == "Дизель"
    assert fuel_label("Benzyna") == "Бензин"


def test_public_lot_url_ok_rejects_broken_peep_links():
    ok = (
        "https://ee.bca-europe.com/Lot?"
        "id=24179092&ItemId=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee&SourceSystem=PEEP"
    )
    bad = (
        "https://ee.bca-europe.com/Lot?"
        "id=0&ItemId=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee&SourceSystem=PEEP"
    )
    assert public_lot_url_ok(ok)
    assert not public_lot_url_ok(bad)
    assert not public_lot_url_ok("https://ee.bca-europe.com/Lot?id=1&SourceSystem=BuyerGateway")


def test_media_download_url_points_at_our_bucket():
    url = media_download_url("bca/abc/inspection_deadbeef.pdf")
    assert url.startswith("/media/object?key=")
    assert url.endswith("&download=1")
    assert "inspection_deadbeef.pdf" in url
    assert media_download_url("../secret.pdf") == ""
    assert media_download_url("/etc/passwd") == ""

