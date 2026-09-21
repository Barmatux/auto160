from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.listing_enrichment import (
    ListingEnrichmentStats,
    RatingOneTarget,
    VinCheckListingFilters,
    VinCheckPageStats,
    VinFoundDateFilter,
    build_vin_check_page_stats,
    format_vin_check_stats_summary,
    listing_matches_rating_one,
    listing_matches_vin_check_filters,
    listing_matches_vin_found_date_filter,
    paginate_rating_one_listings_with_vin,
    normalize_catalog_name,
    perform_listing_vin_check,
    recheck_listing_customs_import_date,
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


def test_admin_vin_found_page_requires_login(client):
    response = client.get("/admin/vin-check/found", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_format_vin_check_stats_summary():
    stats = VinCheckPageStats(
        checks_launched=5,
        checks_success=5,
        vin_by_model=(("Renault Koleos", 1), ("VW Tiguan", 2)),
    )
    text = format_vin_check_stats_summary(stats)
    assert "По 5 vin запущена проверка." in text
    assert "Успешно 5." in text
    assert "Renault Koleos - 1" in text
    assert "VW Tiguan - 2" in text


def test_build_vin_check_page_stats_counts_success_by_model():
    class Listing:
        avby_id = 123
        brand = "VW"
        model = "Tiguan"
        vin = "WVWZZZ1KZAW123456"
        vin_fetched_at = object()

    stats = build_vin_check_page_stats([Listing()])
    assert stats.checks_launched == 1
    assert stats.checks_success == 1
    assert stats.vin_by_model == (("VW Tiguan", 1),)


def test_listing_matches_vin_check_filters():
    auto_diesel = SimpleNamespace(transmission_type="Автомат", engine_type="дизель", year=2021, brand="BMW", model="X1")
    manual_diesel = SimpleNamespace(transmission_type="Механика", engine_type="дизель", year=2019, brand="VW", model="Tiguan")
    auto_petrol = SimpleNamespace(transmission_type="Автомат", engine_type="бензин", year=2020, brand="BMW", model="X3")

    assert listing_matches_vin_check_filters(auto_diesel, VinCheckListingFilters()) is True
    assert listing_matches_vin_check_filters(
        manual_diesel,
        VinCheckListingFilters(only_automatic=True),
    ) is False
    assert listing_matches_vin_check_filters(
        auto_diesel,
        VinCheckListingFilters(only_automatic=True),
    ) is True
    assert listing_matches_vin_check_filters(
        auto_petrol,
        VinCheckListingFilters(only_diesel=True),
    ) is False
    assert listing_matches_vin_check_filters(
        manual_diesel,
        VinCheckListingFilters(only_automatic=True, only_diesel=True),
    ) is False
    assert listing_matches_vin_check_filters(
        auto_diesel,
        VinCheckListingFilters(only_automatic=True, only_diesel=True),
    ) is True
    assert listing_matches_vin_check_filters(
        manual_diesel,
        VinCheckListingFilters(year_from_2020=True),
    ) is False
    assert listing_matches_vin_check_filters(
        auto_petrol,
        VinCheckListingFilters(year_from_2020=True),
    ) is True
    assert listing_matches_vin_check_filters(
        auto_diesel,
        VinCheckListingFilters(only_automatic=True, only_diesel=True, year_from_2020=True),
    ) is True
    assert listing_matches_vin_check_filters(
        auto_diesel,
        VinCheckListingFilters(brand="bmw"),
    ) is True
    assert listing_matches_vin_check_filters(
        auto_petrol,
        VinCheckListingFilters(brand="BMW", model="X1"),
    ) is False
    assert listing_matches_vin_check_filters(
        auto_diesel,
        VinCheckListingFilters(brand="BMW", model="X1"),
    ) is True


def test_listing_matches_vin_found_date_filter():
    from datetime import datetime

    listing = SimpleNamespace(
        vin_fetched_at=datetime(2026, 9, 15, 12, 0, 0),
        created_at=datetime(2026, 9, 10, 8, 0, 0),
    )
    older = SimpleNamespace(
        vin_fetched_at=None,
        created_at=datetime(2026, 9, 1, 8, 0, 0),
    )

    assert listing_matches_vin_found_date_filter(listing, VinFoundDateFilter()) is True
    assert (
        listing_matches_vin_found_date_filter(
            listing,
            VinFoundDateFilter(date_from=date(2026, 9, 15), date_to=date(2026, 9, 15)),
        )
        is True
    )
    assert (
        listing_matches_vin_found_date_filter(
            listing,
            VinFoundDateFilter(date_from=date(2026, 9, 16)),
        )
        is False
    )
    assert (
        listing_matches_vin_found_date_filter(
            older,
            VinFoundDateFilter(date_from=date(2026, 9, 1), date_to=date(2026, 9, 1)),
        )
        is True
    )
    assert VinFoundDateFilter(date_from=date(2026, 9, 15), date_to=date(2026, 9, 16)).label() == (
        "15.09.2026 – 16.09.2026"
    )
    assert VinFoundDateFilter(date_from=date(2026, 9, 15), date_to=date(2026, 9, 15)).label() == "15.09.2026"


def test_listing_matches_vin_found_import_filter():
    from app.listing_enrichment import (
        VinFoundImportFilter,
        listing_matches_vin_found_import_filter,
        months_before,
    )

    today = date(2026, 9, 21)
    assert months_before(today, 10) == date(2025, 11, 21)
    assert months_before(today, 12) == date(2025, 9, 21)

    assert listing_matches_vin_found_import_filter("01.01.2024", VinFoundImportFilter(), today=today) is True
    assert (
        listing_matches_vin_found_import_filter(
            "01.01.2024",
            VinFoundImportFilter(value="gt10"),
            today=today,
        )
        is True
    )
    assert (
        listing_matches_vin_found_import_filter(
            "01.12.2025",
            VinFoundImportFilter(value="gt10"),
            today=today,
        )
        is False
    )
    assert (
        listing_matches_vin_found_import_filter(
            "01.10.2025",
            VinFoundImportFilter(value="gt12"),
            today=today,
        )
        is False
    )
    assert (
        listing_matches_vin_found_import_filter(
            "01.08.2025",
            VinFoundImportFilter(value="gt12"),
            today=today,
        )
        is True
    )
    assert (
        listing_matches_vin_found_import_filter(
            None,
            VinFoundImportFilter(value="unset"),
            today=today,
        )
        is True
    )
    assert (
        listing_matches_vin_found_import_filter(
            "01.01.2024",
            VinFoundImportFilter(value="unset"),
            today=today,
        )
        is False
    )
    assert (
        listing_matches_vin_found_import_filter(
            None,
            VinFoundImportFilter(value="gt10"),
            today=today,
        )
        is False
    )


def test_paginate_rating_one_listings_with_vin_filters_and_pages(monkeypatch):
    listing_with_vin = SimpleNamespace(
        brand="VW",
        model="Tiguan",
        year=2020,
        vin="WVWZZZ1KZAW123456",
    )
    listing_without_vin = SimpleNamespace(
        brand="VW",
        model="Tiguan",
        year=2020,
        vin=None,
    )

    monkeypatch.setattr("app.listing_enrichment.build_rating_one_targets", lambda db: [object()])

    def fake_match(listing, targets):
        return listing in {listing_with_vin, listing_without_vin}

    monkeypatch.setattr("app.listing_enrichment.listing_matches_rating_one", fake_match)

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def yield_per(self, size):
            yield listing_with_vin
            yield listing_without_vin

    db = MagicMock()
    db.query.return_value = FakeQuery()
    page_rows, total = paginate_rating_one_listings_with_vin(db, page=1, page_size=100)
    assert page_rows == [listing_with_vin]
    assert total == 1


def test_build_listing_vin_account_labels_uses_metadata_fallback(monkeypatch):
    listing = SimpleNamespace(id=11, vin="WVWZZZ1KZAW123456", vin_fetched_at=None)

    class FakeQuery:
        def filter(self, *args, **kwargs):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return []

    db = MagicMock()
    db.query.return_value = FakeQuery()
    from app.listing_enrichment import build_listing_vin_account_labels

    monkeypatch.setattr("app.listing_enrichment.listing_has_saved_vin", lambda row: True)
    labels = build_listing_vin_account_labels(db, [listing])
    assert labels[11] == "Из объявления"


def test_recheck_listing_customs_import_date(monkeypatch):
    listing = SimpleNamespace(vin="WVWZZZ1KZAW123456")

    monkeypatch.setattr("app.listing_enrichment.listing_has_saved_vin", lambda row: True)
    def fake_lookup(db, vin, *, database=None, force_refresh=False):
        return SimpleNamespace(found=True, release_date="15.03.2021")

    monkeypatch.setattr("app.listing_enrichment.lookup_customs_vin", fake_lookup)

    release_date, error = recheck_listing_customs_import_date(MagicMock(), listing)
    assert release_date == "15.03.2021"
    assert error is None


def test_apply_manual_listing_vin_rejects_invalid(monkeypatch):
    from app.listing_enrichment import apply_manual_listing_vin

    listing = SimpleNamespace(vin=None, vin_fetched_at=None, vin_indicated=None)
    db = MagicMock()
    result = apply_manual_listing_vin(db, listing, "BADVIN")
    assert result.vin is None
    assert "17" in (result.vin_error or "")
    db.commit.assert_not_called()


def test_apply_manual_listing_vin_saves_and_rechecks(monkeypatch):
    from datetime import datetime

    from app.listing_enrichment import apply_manual_listing_vin

    listing = SimpleNamespace(vin=None, vin_fetched_at=None, vin_indicated=None)
    db = MagicMock()

    monkeypatch.setattr(
        "app.listing_enrichment.recheck_listing_customs_import_date",
        lambda db, row: ("01.02.2020", None),
    )

    result = apply_manual_listing_vin(db, listing, " vf3mrhnsuls192570 ")
    assert result.vin == "VF3MRHNSULS192570"
    assert result.release_date == "01.02.2020"
    assert result.customs_found is True
    assert listing.vin == "VF3MRHNSULS192570"
    assert listing.vin_indicated is True
    assert isinstance(listing.vin_fetched_at, datetime)
    db.commit.assert_called_once()


def test_admin_vin_check_api_requires_auth(client):
    response = client.post("/api/v1/admin/listings/1/vin-check", follow_redirects=False)
    assert response.status_code == 401


def test_admin_vin_manual_api_requires_auth(client):
    response = client.post(
        "/api/v1/admin/listings/1/vin-manual",
        json={"vin": "VF3MRHNSULS192570"},
        follow_redirects=False,
    )
    assert response.status_code == 401


def test_admin_customs_recheck_api_requires_auth(client):
    response = client.post("/api/v1/admin/listings/1/customs-recheck", follow_redirects=False)
    assert response.status_code == 401
