from fastapi.testclient import TestClient

from app.listing_enrichment import RatingOneTarget, listing_matches_rating_one, normalize_catalog_name
from app.main import app

client = TestClient(app)


def test_listing_matches_rating_one_by_make_model_year():
    targets = [
        RatingOneTarget(
            make_n=normalize_catalog_name("BMW"),
            model_n=normalize_catalog_name("X1"),
            year_from=2015,
            year_to=2020,
        )
    ]

    class Listing:
        brand = "BMW"
        model = "X1"
        year = 2018

    class ListingWrongYear:
        brand = "BMW"
        model = "X1"
        year = 2010

    assert listing_matches_rating_one(Listing(), targets) is True
    assert listing_matches_rating_one(ListingWrongYear(), targets) is False


def test_admin_vin_check_page_requires_login():
    response = client.get("/admin/vin-check", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_admin_vin_check_api_requires_auth():
    response = client.post("/api/v1/admin/listings/1/vin-check", follow_redirects=False)
    assert response.status_code == 401
