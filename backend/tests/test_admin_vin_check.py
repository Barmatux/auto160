from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.listing_enrichment import (
    ListingEnrichmentStats,
    RatingOneTarget,
    listing_matches_rating_one,
    normalize_catalog_name,
    perform_listing_vin_check,
)


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


def test_perform_listing_vin_check_uses_inactive_accounts(monkeypatch):
    listing = SimpleNamespace(id=7, vin="WBAINACTIVE0000001", avby_id=123)
    seen: dict[str, bool] = {}

    def fake_enrich(db, row, *, sync_run_id=None, allow_inactive=False):
        seen["allow_inactive"] = allow_inactive
        return ListingEnrichmentStats(attempted=1, vin_fetched=1)

    monkeypatch.setattr("app.listing_enrichment.enrich_listing_vin_and_customs", fake_enrich)
    monkeypatch.setattr(
        "app.listing_enrichment.get_listing_customs_summary",
        lambda db, row: SimpleNamespace(found=True, release_date="01.01.2020"),
    )
    monkeypatch.setattr("app.listing_enrichment.listing_has_saved_vin", lambda row: True)

    db = MagicMock()
    result = perform_listing_vin_check(db, listing)
    assert seen["allow_inactive"] is True
    assert result.vin == "WBAINACTIVE0000001"
    assert result.release_date == "01.01.2020"


@pytest.fixture
def client():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_admin_vin_check_page_requires_login(client):
    response = client.get("/admin/vin-check", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_admin_vin_check_api_requires_auth(client):
    response = client.post("/api/v1/admin/listings/1/vin-check", follow_redirects=False)
    assert response.status_code == 401
