from app.listing_display import (
    listing_display_description,
    listing_display_title,
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
