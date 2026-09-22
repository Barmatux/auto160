from app.auto24_map import parse_engine_field, _cdn_photo_urls


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


def test_cdn_photo_urls_preferred_from_parameters():
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
