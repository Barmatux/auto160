from app.bca_admin import (
    _parse_sync_utc,
    canonical_peep_lot_url,
    corrected_mileage,
    country_label,
    format_auction_start,
    fuel_label,
    media_download_url,
    public_lot_url_ok,
)


def test_corrected_mileage_drops_trailing_decimal_zero():
    assert corrected_mileage(1463080) == 146308
    assert corrected_mileage(25812) == 25812
    assert corrected_mileage(None) is None


def test_country_and_fuel_labels():
    assert country_label("DE") == "Германия (DE)"
    assert fuel_label("BEV - battery electric vehicle  100% electric") == "Электро"
    assert fuel_label("Diesel") == "Дизель"
    assert fuel_label("Benzyna") == "Бензин"


def test_parse_sync_utc_from_bca_iso():
    parsed = _parse_sync_utc("2026-11-26T13:30:00Z")
    assert parsed is not None
    assert format_auction_start(parsed) == "26.11.2026 13:30 UTC"


def test_canonical_peep_lot_url_adds_page_and_encodes_bq():
    raw = (
        "https://ee.bca-europe.com/Lot?id=24186345&ItemId=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        "&bq=saleid_exact:c3501219-972a-4785-9775-3fea7d41e8fb"
        "&SourceSystem=PEEP"
    )
    fixed = canonical_peep_lot_url(raw)
    assert "page=1" in fixed
    assert "saleid_exact%3A" in fixed
    assert "saleid_exact:" not in fixed.split("?", 1)[-1]


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

