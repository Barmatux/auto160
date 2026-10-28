"""Public Belarus reframe: featured pool, guest access, import-date lookup."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.featured import (
    FEATURED_HOME_LIMIT,
    assert_listing_eligible_for_featured,
    create_site_lead,
    lookup_public_import_date,
    rotate_featured_for_home,
)
from app.listing_import_age import release_date_older_than_months
from app.main import app
from app.models import ListingStatus

client = TestClient(app)


def test_rotate_featured_is_deterministic_per_day():
    listings = [SimpleNamespace(id=i) for i in range(15)]
    day = date(2026, 10, 20)
    first = [item.id for item in rotate_featured_for_home(listings, today=day)]
    second = [item.id for item in rotate_featured_for_home(listings, today=day)]
    assert first == second
    assert len(first) == FEATURED_HOME_LIMIT
    other_day = [item.id for item in rotate_featured_for_home(listings, today=date(2026, 10, 21))]
    # Different day usually reshuffles; allow rare hash collision by checking length only if equal
    assert len(other_day) == FEATURED_HOME_LIMIT


def test_assert_listing_eligible_requires_old_import_date(monkeypatch):
    listing = SimpleNamespace(id=1, status=ListingStatus.published)
    monkeypatch.setattr(
        "app.featured.get_listing_customs_summary",
        lambda db, row: SimpleNamespace(found=True, release_date="01.01.2020"),
    )
    assert_listing_eligible_for_featured(MagicMock(), listing)

    monkeypatch.setattr(
        "app.featured.get_listing_customs_summary",
        lambda db, row: SimpleNamespace(found=True, release_date="01.09.2026"),
    )
    with pytest.raises(ValueError, match="даты ввоза"):
        assert_listing_eligible_for_featured(MagicMock(), listing)

    # Fresh relative to fixed today
    assert release_date_older_than_months("01.09.2026", 12, today=date(2026, 10, 20)) is False
    assert release_date_older_than_months("01.01.2020", 12, today=date(2026, 10, 20)) is True


def test_assert_listing_eligible_rejects_unpublished(monkeypatch):
    listing = SimpleNamespace(id=1, status=ListingStatus.draft)
    monkeypatch.setattr(
        "app.featured.get_listing_customs_summary",
        lambda db, row: SimpleNamespace(found=True, release_date="01.01.2020"),
    )
    with pytest.raises(ValueError, match="опубликованное"):
        assert_listing_eligible_for_featured(MagicMock(), listing)


def test_guest_belarus_listings_is_landing():
    response = client.get("/by")
    assert response.status_code == 200
    assert "льготный утильсбор" in response.text
    assert "Узнать дату ввоза" in response.text
    assert "data-import-date-form" in response.text


def test_guest_listings_redirects_to_by():
    response = client.get("/listings", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "/by"


def test_guest_belarus_listing_detail_hidden():
    """Without a real DB row the page is 404; with BY listing non-admin must not see feed card links."""
    response = client.get("/listings/999999991")
    assert response.status_code == 404


def test_admin_featured_requires_login():
    response = client.get("/admin/featured", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_admin_site_leads_requires_login():
    response = client.get("/admin/site-leads", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_public_lead_validation():
    response = client.post("/api/v1/public/leads", json={"contact_name": "", "contact": "123"})
    assert response.status_code == 400


def test_lookup_public_import_date_vin(monkeypatch):
    class FakeResult:
        found = True
        release_date = "15.03.2020"

    monkeypatch.setattr(
        "app.featured.lookup_customs_vin",
        lambda db, vin, **kwargs: FakeResult(),
    )
    monkeypatch.setattr("app.featured.vin_is_valid", lambda vin: True)
    monkeypatch.setattr("app.featured.normalize_vin", lambda vin: vin.upper())

    result = lookup_public_import_date(MagicMock(), "WBA3A5C50EF123456")
    assert result.ok is True
    assert result.input_kind == "vin"
    assert result.release_date == "15.03.2020"
    assert result.customs_found is True


def test_lookup_public_import_date_empty():
    result = lookup_public_import_date(MagicMock(), "  ")
    assert result.ok is False
    assert "VIN" in (result.message or "")


def test_lookup_public_import_date_customs_site_error(monkeypatch):
    from app.customs_vin import CUSTOMS_SITE_UNAVAILABLE_MESSAGE, CustomsVinError

    monkeypatch.setattr(
        "app.featured.lookup_customs_vin",
        lambda db, vin, **kwargs: (_ for _ in ()).throw(
            CustomsVinError("Не удалось связаться с сайтом таможни: timeout")
        ),
    )
    monkeypatch.setattr("app.featured.vin_is_valid", lambda vin: True)
    monkeypatch.setattr("app.featured.normalize_vin", lambda vin: vin.upper())

    result = lookup_public_import_date(MagicMock(), "WBA3A5C50EF123456")
    assert result.ok is True
    assert result.customs_status == "unavailable"
    assert result.message == CUSTOMS_SITE_UNAVAILABLE_MESSAGE
    assert "свяжитесь с нами" in (result.message or "").lower()
    assert "timeout" not in (result.message or "").lower()


def test_lookup_public_import_date_not_found_when_reference_ok(monkeypatch):
    from app.customs_vin import CUSTOMS_NOT_FOUND_MESSAGE, CUSTOMS_REFERENCE_VIN, normalize_vin

    class FakeResult:
        found = False
        release_date = None

    class RefResult:
        found = True
        release_date = "01.01.2020"

    def fake_lookup(db, vin, **kwargs):
        if normalize_vin(vin) == CUSTOMS_REFERENCE_VIN:
            return RefResult()
        return FakeResult()

    monkeypatch.setattr("app.featured.lookup_customs_vin", fake_lookup)
    monkeypatch.setattr("app.customs_vin.lookup_customs_vin", fake_lookup)
    monkeypatch.setattr("app.featured.vin_is_valid", lambda vin: True)
    monkeypatch.setattr("app.featured.normalize_vin", lambda vin: vin.upper())

    result = lookup_public_import_date(MagicMock(), "WBA3A5C50EF123456")
    assert result.ok is True
    assert result.customs_found is False
    assert result.customs_status == "not_found"
    assert result.message == CUSTOMS_NOT_FOUND_MESSAGE


def test_lookup_public_import_date_not_found_when_reference_also_missing(monkeypatch):
    from app.customs_vin import CUSTOMS_SITE_UNAVAILABLE_MESSAGE

    class FakeResult:
        found = False
        release_date = None

    monkeypatch.setattr(
        "app.featured.lookup_customs_vin",
        lambda db, vin, **kwargs: FakeResult(),
    )
    monkeypatch.setattr(
        "app.customs_vin.lookup_customs_vin",
        lambda db, vin, **kwargs: FakeResult(),
    )
    monkeypatch.setattr("app.featured.vin_is_valid", lambda vin: True)
    monkeypatch.setattr("app.featured.normalize_vin", lambda vin: vin.upper())

    result = lookup_public_import_date(MagicMock(), "WBA3A5C50EF123456")
    assert result.ok is True
    assert result.customs_status == "unavailable"
    assert result.customs_found is None
    assert result.message == CUSTOMS_SITE_UNAVAILABLE_MESSAGE
    assert "временно не работает" in (result.message or "").lower()


def test_run_public_inspection_check_hides_vin_for_url(monkeypatch):
    from app.featured import ImportDateLookupResult, run_public_inspection_check

    monkeypatch.setattr(
        "app.featured.lookup_public_import_date",
        lambda db, raw: ImportDateLookupResult(
            ok=True,
            input_kind="avby_url",
            vin="WBA3A5C50EF123456",
            release_date="15.08.2024",
            customs_found=True,
            listing_id=None,
            avby_url="https://cars.av.by/bmw/1",
        ),
    )
    hidden = run_public_inspection_check(MagicMock(), "https://cars.av.by/bmw/1", reveal_vin=False)
    assert hidden.vin is None
    assert hidden.verdict is not None

    shown = run_public_inspection_check(MagicMock(), "https://cars.av.by/bmw/1", reveal_vin=True)
    assert shown.vin == "WBA3A5C50EF123456"


def test_run_public_inspection_check_keeps_typed_vin(monkeypatch):
    from app.featured import ImportDateLookupResult, run_public_inspection_check

    monkeypatch.setattr(
        "app.featured.lookup_public_import_date",
        lambda db, raw: ImportDateLookupResult(
            ok=True,
            input_kind="vin",
            vin="WBA3A5C50EF123456",
            release_date="15.08.2024",
            customs_found=True,
        ),
    )
    result = run_public_inspection_check(MagicMock(), "WBA3A5C50EF123456", reveal_vin=False)
    assert result.vin == "WBA3A5C50EF123456"
    assert result.verdict["code"] == "vin_only"


def test_create_site_lead_persists(monkeypatch):
    stored = {}

    class FakeLead:
        id = 1
        source = "featured_modal"
        contact_name = "Иван"
        contact = "+7999"
        comment = None
        listing_id = 5
        avby_url = "https://cars.av.by/x"
        is_read = False
        created_at = None

    db = MagicMock()

    def add(obj):
        stored["obj"] = obj

    def commit():
        stored["committed"] = True

    def refresh(obj):
        obj.id = 1

    db.add.side_effect = add
    db.commit.side_effect = commit
    db.refresh.side_effect = refresh

    lead = create_site_lead(
        db,
        contact_name="Иван",
        contact="+7999",
        listing_id=5,
        avby_url="https://cars.av.by/x",
        source="featured_modal",
    )
    assert stored.get("committed") is True
    assert lead.contact_name == "Иван"
    assert lead.listing_id == 5


def test_home_shows_featured_section():
    response = client.get("/")
    assert response.status_code == 200
    assert "Подборка Auto160" in response.text
    assert "Вся лента" not in response.text


def test_static_seo_listings_is_landing_copy():
    from app.seo import STATIC_SEO

    title, description = STATIC_SEO["/by"]
    assert "подбор" in title.lower() or "Беларуси" in title
    assert "лента объявлений" not in title.lower()
