from app.listing_missing_byn import apply_import_byn_price_state
from app.models import CarListing, ListingStatus


def _listing(**kwargs) -> CarListing:
    defaults = {
        "seller_id": 1,
        "title": "Test",
        "brand": "Peugeot",
        "model": "308",
        "year": 2022,
        "mileage": 1,
        "price": 46_533,
        "price_byn_missing": False,
        "city": "Minsk",
        "description": "x",
        "status": ListingStatus.published,
    }
    defaults.update(kwargs)
    return CarListing(**defaults)


def test_apply_import_byn_price_state_marks_draft_when_missing():
    listing = _listing()
    apply_import_byn_price_state(listing, price_byn=None, price_byn_missing=True)
    assert listing.price is None
    assert listing.price_byn_missing is True
    assert listing.status == ListingStatus.draft


def test_apply_import_byn_price_state_publishes_when_byn_arrives():
    listing = _listing(status=ListingStatus.draft, price=None, price_byn_missing=True)
    apply_import_byn_price_state(listing, price_byn=46_533.24, price_byn_missing=False)
    assert listing.price == 46_533.24
    assert listing.price_byn_missing is False
    assert listing.status == ListingStatus.published
