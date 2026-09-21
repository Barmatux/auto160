from datetime import datetime
from unittest.mock import MagicMock

from app.listing_display import is_legal_entity_seller, listing_seller_label
from app.models import CarListing, ListingStatus
from app.seller_analytics import (
    BusinessSellerSort,
    build_business_seller_listings,
    build_business_seller_report,
    normalize_seller_key,
)


def _listing(**kwargs) -> CarListing:
    defaults = dict(
        title="Test",
        brand="BMW",
        model="X1",
        year=2019,
        mileage=10000,
        price=20000,
        price_byn_missing=False,
        city="Минск",
        description="x",
        seller_id=1,
        status=ListingStatus.published,
        source="av.by",
        created_at=datetime(2026, 1, 10),
        avby_published_at=datetime(2026, 1, 5),
        avby_renewed_at=datetime(2026, 2, 1),
    )
    defaults.update(kwargs)
    return CarListing(**defaults)


def test_is_legal_entity_seller():
    assert is_legal_entity_seller('ООО "Автомир"')
    assert is_legal_entity_seller("ИП Иванов И.И.")
    assert not is_legal_entity_seller("Иван")
    assert not is_legal_entity_seller(None)
    assert listing_seller_label("ООО Ромашка") == "ООО Ромашка"
    assert listing_seller_label("Петр") == "Частное лицо"


def test_normalize_seller_key_collapses_case_and_spaces():
    assert normalize_seller_key("  ООО  Авто  ") == normalize_seller_key("ооо авто")


def test_build_business_seller_report_groups_and_sums():
    listings = [
        _listing(
            id=1,
            seller_name='ООО "Автомир"',
            status=ListingStatus.published,
            price=10000,
            cover_photo_url="/media/x",
        ),
        _listing(
            id=2,
            seller_name='ооо "автомир"',
            status=ListingStatus.archived,
            price=15000,
            avby_published_at=datetime(2025, 12, 1),
            avby_renewed_at=datetime(2026, 3, 1),
            vin="WBAHT31030F123456",
        ),
        _listing(id=3, seller_name="Иван", status=ListingStatus.published, price=9000),
        _listing(
            id=4,
            seller_name="ИП Петров",
            status=ListingStatus.published,
            price=5000,
            city="Гродно",
        ),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = listings

    summary, rows = build_business_seller_report(db, sort=BusinessSellerSort(sort="total", direction="desc"))
    assert summary.sellers_count == 2
    assert summary.listings_total == 3
    assert summary.published_total == 2
    assert summary.archived_total == 1
    assert summary.archived_sum_byn == 15000

    top = rows[0]
    assert "автомир" in top.seller_name.casefold() or "Автомир" in top.seller_name
    assert top.total == 2
    assert top.published == 1
    assert top.archived == 1
    assert top.published_sum_byn == 10000
    assert top.archived_sum_byn == 15000
    assert top.with_vin == 1
    assert top.with_photo == 1
    assert top.opened_at == datetime(2025, 12, 1)
    assert top.last_activity_at == datetime(2026, 3, 1)


def test_build_business_seller_listings_detail():
    listings = [
        _listing(id=10, seller_name="ООО Тест", status=ListingStatus.published, price=3000),
        _listing(id=11, seller_name="ООО Тест", status=ListingStatus.archived, price=4000),
        _listing(id=12, seller_name="Другой", status=ListingStatus.published, price=1000),
    ]
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = listings

    stats, rows = build_business_seller_listings(db, "ООО Тест")
    assert stats is not None
    assert stats.total == 2
    assert stats.archived_sum_byn == 4000
    assert len(rows) == 2
