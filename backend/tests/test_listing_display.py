from app.listing_display import (
    format_listing_spec_value,
    format_mileage_km,
    format_price_rub,
    listing_display_description,
    listing_display_title,
    listing_engine_summary,
    listing_seller_label,
    listing_source_href,
    listing_source_label,
)
from app.models import CarListing


def _listing(**kwargs) -> CarListing:
    return CarListing(
        title="Test",
        brand="BMW",
        model="X1",
        year=2019,
        mileage=1,
        price=1,
        city="Minsk",
        description="x",
        seller_id=1,
        **kwargs,
    )


def test_listing_display_title_strips_avby_suffix():
    assert listing_display_title("BMW X1 2019 (av.by #1234567)") == "BMW X1 2019"


def test_listing_source_label_shows_host_and_path():
    assert (
        listing_source_label("https://cars.av.by/1234567")
        == "cars.av.by/1234567"
    )


def test_listing_source_href_falls_back_to_avby_id():
    listing = _listing(avby_id=999, source_url=None)
    assert listing_source_href(listing) == "https://cars.av.by/999"


def test_listing_display_description_strips_import_metadata():
    description = (
        "Живой автомобиль.\n\n"
        "Источник: av.by\n"
        "URL: https://cars.av.by/123\n"
        "AVBY_ID: 123"
    )
    assert listing_display_description(description) == "Живой автомобиль."


def test_format_mileage_km_uses_thousands_separator():
    assert format_mileage_km(123456) == "123 456"
    assert format_mileage_km(86000) == "86 000"


def test_format_price_rub_uses_thousands_separator():
    assert format_price_rub(27400) == "27 400"
    assert format_price_rub(1234567) == "1 234 567"
    assert format_price_rub(27400.50) == "27 400,50"


def test_format_listing_spec_value_capitalizes_first_letter():
    assert format_listing_spec_value("автомат") == "Автомат"
    assert format_listing_spec_value("полный") == "Полный"
    assert format_listing_spec_value("Автомат") == "Автомат"


def test_listing_seller_label():
    assert listing_seller_label("Александр") == "Частное лицо"
    assert listing_seller_label('ООО «АвтоМир»') == 'ООО «АвтоМир»'
    assert listing_seller_label(None) == "Частное лицо"


def test_listing_engine_summary():
    listing = _listing(engine_capacity_l=3.0, engine_power_hp=340, engine_type="Бензин")
    assert listing_engine_summary(listing) == "3.0 л, 340 л.с., бензин"
