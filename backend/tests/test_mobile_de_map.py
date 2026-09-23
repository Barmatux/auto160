from app.mobile_de_map import map_mobile_de_row, parse_engine_field


def test_parse_engine_cm3_and_ps():
    liters, hp = parse_engine_field("1.499 cm³, 103 kW (140 PS)")
    assert liters == 1.499
    assert hp == 140


def test_parse_engine_cm3_without_thousands():
    liters, hp = parse_engine_field("999 cm³, 70 kW (95 PS)")
    assert liters == 0.999
    assert hp == 95


def test_parse_engine_kw_only_fallback():
    liters, hp = parse_engine_field("150 kW (204 PS)")
    assert liters is None
    assert hp == 204


def test_map_mobile_de_row_s3_photos_and_labels():
    row = {
        "external_id": "459746321",
        "title": "BMW 218 Gran Tourer in Teltow | mobile.de",
        "year": 2018,
        "price_eur": 14999,
        "mileage_km": 110781,
        "city": "14513 Teltow",
        "body_type": "Van/Minibus",
        "fuel": "Benzin",
        "transmission": "Automatik",
        "engine": "1.499 cm³, 103 kW (140 PS)",
        "url": "https://suchen.mobile.de/fahrzeuge/details.html?id=459746321",
        "photo_url": "/media/object?key=mobile_de%2F459746321%2F000_abc.jpg",
        "photo_urls": ["/media/object?key=mobile_de%2F459746321%2F000_abc.jpg"],
        "detail_scraped": True,
        "parameters": {
            "make": "BMW",
            "model": "218 Gran Tourer in Teltow | mobile.de",
            "power": "103 kW (140 PS)",
            "displacement": "1.499 cm³",
        },
    }
    mapped = map_mobile_de_row(row, eur_rate=None, max_hp=None, max_age_years=None, max_engine_l=None)
    assert mapped.skip_reason is None
    assert mapped.brand == "BMW"
    assert mapped.model == "218 Gran Tourer"
    assert mapped.city == "Teltow"
    assert mapped.body_type == "Минивэн"
    assert mapped.engine_type == "Бензин"
    assert mapped.transmission_type == "Автоматическая"
    assert mapped.engine_capacity_l == 1.499
    assert mapped.engine_power_hp == 140
    assert mapped.photo_storage_keys == ["mobile_de/459746321/000_abc.jpg"]
    assert mapped.cover_photo_url == "/media/object?key=mobile_de%2F459746321%2F000_abc.jpg"


def test_map_skips_overpowered():
    row = {
        "external_id": "1",
        "title": "Audi TT in X | mobile.de",
        "year": 2022,
        "price_eur": 20000,
        "mileage_km": 10000,
        "city": "Berlin",
        "body_type": "Cabrio/Roadster",
        "fuel": "Benzin",
        "transmission": "Automatik",
        "engine": "1.984 cm³, 169 kW (230 PS)",
        "url": "https://suchen.mobile.de/x",
        "detail_scraped": True,
        "parameters": {"make": "Audi", "model": "TT in X | mobile.de"},
    }
    mapped = map_mobile_de_row(row, eur_rate=None, max_hp=160, max_age_years=5, max_engine_l=1.9)
    assert mapped.skip_reason == "hp_over_160"
