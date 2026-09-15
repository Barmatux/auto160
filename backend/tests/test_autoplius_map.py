from decimal import Decimal

from app.autoplius_map import (
    EurRate,
    extract_engine_power_hp,
    map_autoplius_row,
    parse_brand_model,
    parse_year,
)


def test_parse_brand_model_simple():
    assert parse_brand_model("Toyota RAV4, 2.2 l., SUV 2007 m.") == ("Toyota", "RAV4")
    assert parse_brand_model("BMW 520, 2.0 l., Универсал 2019-12 m.") == ("BMW", "520")
    assert parse_brand_model("Mercedes-Benz GLC Coupe 220, 2.1 l., ...") == ("Mercedes-Benz", "GLC Coupe 220")


def test_parse_year():
    assert parse_year("2019-12") == 2019
    assert parse_year("2007") == 2007
    assert parse_year(None) is None


def test_extract_hp_from_raw_parameters():
    row = {
        "parameters": {},
        "raw": {
            "parameters": {
                "Двигатель": "1598 см³, 160 Л.С. (118кВ)",
            }
        },
    }
    assert extract_engine_power_hp(row) == 160


def test_map_skips_overpowered():
    rate = EurRate(rate=3.5, scale=1, rate_date=__import__("datetime").date(2026, 9, 14))
    row = {
        "external_id": "1",
        "title": "BMW 520, 2.0 l., Универсал 2019 m.",
        "year": "2019",
        "price_eur": 20000,
        "mileage_km": 100000,
        "city": "Вильнюс",
        "body_type": "Универсал",
        "fuel": "Дизель",
        "transmission": "Автоматическая",
        "engine_liters": 2.0,
        "url": "https://example.test/1",
        "photo_url": "/media/object?key=listings%2F1%2F000_a.jpg",
        "photo_urls": ["/media/object?key=listings%2F1%2F000_a.jpg"],
        "detail_scraped": True,
        "raw": {"parameters": {"Двигатель": "1995 см³, 190 Л.С."}},
        "parameters": {},
    }
    mapped = map_autoplius_row(row, eur_rate=rate, max_hp=160)
    assert mapped.skip_reason == "hp_over_160"
    assert mapped.price_byn == Decimal("70000.00")
    assert mapped.photo_storage_keys == ["listings/1/000_a.jpg"]
    assert mapped.cover_photo_url == "/media/autoplius?key=listings%2F1%2F000_a.jpg"


def test_extract_storage_key_from_media_proxy():
    from app.autoplius_map import extract_storage_key

    assert (
        extract_storage_key("/media/object?key=listings%2F29526558%2F000_x.jpg")
        == "listings/29526558/000_x.jpg"
    )
