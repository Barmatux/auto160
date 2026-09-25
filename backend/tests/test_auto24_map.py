from app.auto24_map import (
    map_auto24_row,
    parse_engine_field,
    parse_registration_ym,
    extract_registration_ym,
    _cdn_photo_urls,
    _city,
)


def test_parse_engine_liters_and_kw():
    liters, hp = parse_engine_field("1.5 71kW")
    assert liters == 1.5
    assert hp == 97  # round(71 * 1.35962)


def test_parse_engine_kw_only_no_false_liters():
    liters, hp = parse_engine_field("70kW")
    assert liters is None
    assert hp == 95


def test_parse_engine_from_title():
    liters, hp = parse_engine_field(None, "Ford Focus 1.5 71kW")
    assert liters == 1.5
    assert hp == 97


def test_parse_registration_ym_formats():
    assert parse_registration_ym("2023-01") == "2023-01"
    assert parse_registration_ym("2023/1") == "2023-01"
    assert parse_registration_ym("01.2023") == "2023-01"
    assert parse_registration_ym("1/2023") == "2023-01"
    assert parse_registration_ym("2023") is None


def test_extract_registration_ym_from_parameters():
    assert (
        extract_registration_ym(
            {"year": 2021, "parameters": {"first_registration": "03/2021"}}
        )
        == "2021-03"
    )


def test_cdn_photo_urls_from_parameters():
    urls = _cdn_photo_urls(
        {
            "photo_url": "/media/object?key=auto24%2Fx%2F000.jpg",
            "parameters": {
                "source_photo_urls": [
                    "https://img13.img-bcg.eu/h30/abc/s1/1.jpg",
                    "https://img13.img-bcg.eu/h30/abc/s1/2.jpg",
                ]
            },
        }
    )
    assert urls == [
        "https://img13.img-bcg.eu/h30/abc/s1/1.jpg",
        "https://img13.img-bcg.eu/h30/abc/s1/2.jpg",
    ]


def test_city_from_parameters_location():
    assert _city({"city": None, "parameters": {"location": "Tallinn"}}) == "Tallinn"
    assert _city({"city": "Эстония", "parameters": {"Asukoht": "Tartu"}}) == "Tartu"
    assert _city({"city": "Estonia"}) is None
    assert (
        _city(
            {
                "parameters": {
                    "specs": [{"name": "Asukoht", "value": "Pärnu"}],
                }
            }
        )
        == "Pärnu"
    )


def test_map_embeds_registration_month_in_title():
    row = {
        "external_id": "123",
        "title": "Ford Focus 1.5 71kW",
        "year": "2020-06",
        "price_eur": 10000,
        "mileage_km": 50000,
        "city": None,
        "body_type": "sedaan",
        "fuel": "bensiin",
        "transmission": "manuaal",
        "engine": "1.5 71kW",
        "url": "https://www.auto24.ee/x",
        "photo_url": "/media/object?key=auto24%2F123%2F000_abc.jpg",
        "photo_urls": ["/media/object?key=auto24%2F123%2F000_abc.jpg"],
        "detail_scraped": True,
        "parameters": {
            "location": "Tallinn",
            "source_photo_urls": ["https://img13.img-bcg.eu/h30/abc/s1/1.jpg"],
        },
    }
    mapped = map_auto24_row(row, eur_rate=None, max_hp=None, max_age_years=None, max_engine_l=None)
    assert mapped.skip_reason is None
    assert mapped.year == 2020
    assert mapped.city == "Tallinn"
    assert "2020-06 m." in mapped.title
    assert mapped.photo_storage_keys == ["auto24/123/000_abc.jpg"]
    assert mapped.cover_photo_url == "/media/object?key=auto24%2F123%2F000_abc.jpg"
    assert mapped.photo_urls == ["/media/object?key=auto24%2F123%2F000_abc.jpg"]
