from app.listing_display import (
    format_listing_spec_value,
    format_mileage_km,
    format_vin_found_specs_line,
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
    defaults = dict(
        title="Test",
        brand="BMW",
        model="X1",
        year=2019,
        mileage=1,
        price=1,
        city="Minsk",
        description="x",
        seller_id=1,
    )
    defaults.update(kwargs)
    return CarListing(**defaults)


def test_listing_display_title_strips_avby_suffix():
    assert listing_display_title("BMW X1 2019 (av.by #1234567)") == "BMW X1 2019"


def test_listing_feed_heading_autoplius_uses_registration_month():
    from app.listing_display import listing_feed_heading

    listing = _listing(
        source="autoplius",
        brand="Hyundai",
        model="i10",
        year=2023,
        title="Hyundai i10, 1.0 l., Хэтчбек 2023-01 m., | A30330493",
    )
    assert listing_feed_heading(listing) == "Hyundai i10 · 2023-01"


def test_listing_feed_heading_auto24_uses_registration_month():
    from app.listing_display import (
        listing_feed_heading,
        listing_registration_date_label,
        listing_registration_date_value,
    )

    listing = _listing(
        source="auto24",
        brand="Hyundai",
        model="i10",
        year=2023,
        title="Hyundai i10 1.0 49kW 2023-01 m.",
    )
    assert listing_feed_heading(listing) == "Hyundai i10 · 2023-01"
    assert listing_registration_date_label(listing) == "Дата первой регистрации"
    assert listing_registration_date_value(listing) == "2023-01"


def test_listing_feed_heading_belarus_puts_generation_before_year():
    from app.listing_display import listing_feed_heading

    listing = _listing(
        source="av.by",
        brand="Nissan",
        model="Qashqai",
        generation="II",
        year=2014,
        title="Nissan Qashqai 2014 (av.by #1)",
    )
    assert listing_feed_heading(listing) == "Nissan Qashqai II 2014"


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


def test_format_vin_found_specs_line():
    listing = _listing(
        engine_capacity_l=1.2,
        engine_type="Бензин",
        transmission_type="Робот",
        mileage=196000,
    )
    assert format_vin_found_specs_line(listing) == "1.2 бензин робот 196.000км"


def test_format_vin_found_specs_line_formats_whole_liters_with_decimal():
    listing = _listing(engine_capacity_l=2, engine_type="Бензин", mileage=50000)
    assert format_vin_found_specs_line(listing) == "2.0 бензин 50.000км"


def test_listing_location_display_joins_country_and_city():
    from app.listing_display import listing_location_display

    by_listing = _listing(source="av.by", city="Минск")
    assert listing_location_display(by_listing) == "Беларусь, Минск"

    lt_listing = _listing(source="autoplius", city="Vilnius")
    assert listing_location_display(lt_listing) == "Литва, Vilnius"

    country_only = _listing(source="auto24", city="Эстония")
    assert listing_location_display(country_only) == "Эстония"


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
