from datetime import datetime
from unittest.mock import MagicMock

from app.listing_display import is_legal_entity_seller, listing_seller_label
from app.models import CarListing, ListingAvgPrice, ListingStatus
from app.seller_analytics import (
    BusinessSellerSort,
    build_business_seller_listings,
    build_business_seller_report,
    format_vs_market_label,
    listing_vs_market_pct,
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


def _db_with_listings_and_avgs(listings, avgs=None):
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model is CarListing:
            q.options.return_value = q
            q.filter.return_value = q
            q.order_by.return_value = q
            q.all.return_value = listings
        elif model is ListingAvgPrice:
            q.filter.return_value = q
            q.all.return_value = avgs or []
        else:
            q.filter.return_value = q
            q.all.return_value = []
        return q

    db.query.side_effect = query_side_effect
    return db


def test_is_legal_entity_seller():
    assert is_legal_entity_seller('ООО "Автомир"')
    assert is_legal_entity_seller("ИП Иванов И.И.")
    assert not is_legal_entity_seller("Иван")
    assert not is_legal_entity_seller(None)
    assert listing_seller_label("ООО Ромашка") == "ООО Ромашка"
    assert listing_seller_label("Петр") == "Частное лицо"


def test_normalize_seller_key_collapses_case_and_spaces():
    assert normalize_seller_key("  ООО  Авто  ") == normalize_seller_key("ооо авто")


def test_format_vs_market_label():
    assert format_vs_market_label(None) == "—"
    assert format_vs_market_label(12.5, compared=3) == "выше рынка на 12.5%"
    assert format_vs_market_label(-8.0, compared=2) == "ниже рынка на 8.0%"
    assert "рынок" in format_vs_market_label(1.2, compared=1)


def test_listing_vs_market_pct():
    listing = _listing(brand="BMW", model="X1", year=2019, price=22000)
    avg_map = {("bmw", "x1", 2019): 20000.0}
    assert listing_vs_market_pct(listing, avg_map) == 10.0
    assert listing_vs_market_pct(_listing(price=18000), avg_map) == -10.0
    assert listing_vs_market_pct(_listing(brand="Audi"), avg_map) is None


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
    db = _db_with_listings_and_avgs(listings)

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


def test_build_business_seller_report_vs_market():
    listings = [
        _listing(id=1, seller_name="ООО Тест", brand="BMW", model="X1", year=2019, price=22000),
        _listing(id=2, seller_name="ООО Тест", brand="BMW", model="X1", year=2019, price=18000),
        _listing(id=3, seller_name="ООО Тест", brand="Audi", model="A4", year=2018, price=15000),
    ]
    avgs = [
        ListingAvgPrice(
            brand="BMW",
            model="X1",
            year=2019,
            avg_price_byn=20000,
            sample_count=20,
            sample_count_raw=20,
            outliers_removed=0,
            window_days=90,
            window_start=datetime(2025, 12, 1),
            window_end=datetime(2026, 3, 1),
        )
    ]
    db = _db_with_listings_and_avgs(listings, avgs)
    _summary, rows = build_business_seller_report(db)
    assert len(rows) == 1
    row = rows[0]
    assert row.vs_market_compared == 2
    assert row.vs_market_above == 1
    assert row.vs_market_below == 1
    assert row.vs_market_avg_pct == 0.0
    assert "рынок" in row.vs_market_label


def test_listing_days_on_market():
    from app.seller_analytics import format_listing_lifetime_label, listing_days_on_market

    now = datetime(2026, 3, 15)
    published = _listing(
        status=ListingStatus.published,
        avby_published_at=datetime(2026, 3, 1),
        avby_renewed_at=datetime(2026, 3, 10),
    )
    assert listing_days_on_market(published, now=now) == 14
    assert format_listing_lifetime_label(published, 14) == "висит 14 дн."

    archived = _listing(
        status=ListingStatus.archived,
        avby_published_at=datetime(2026, 1, 1),
        avby_renewed_at=datetime(2026, 1, 21),
    )
    assert listing_days_on_market(archived, now=now) == 20
    assert "прожило" in format_listing_lifetime_label(archived, 20)


def test_build_business_seller_report_lifetime_avg():
    now = datetime(2026, 3, 15)
    listings = [
        _listing(
            id=1,
            seller_name="ООО Срок",
            status=ListingStatus.published,
            avby_published_at=datetime(2026, 3, 5),
            avby_renewed_at=datetime(2026, 3, 10),
        ),
        _listing(
            id=2,
            seller_name="ООО Срок",
            status=ListingStatus.archived,
            avby_published_at=datetime(2026, 1, 1),
            avby_renewed_at=datetime(2026, 1, 31),
        ),
    ]
    db = _db_with_listings_and_avgs(listings)
    import app.seller_analytics as mod

    original = mod.datetime

    class _FixedDatetime(datetime):
        @classmethod
        def utcnow(cls):
            return now

    mod.datetime = _FixedDatetime  # type: ignore[misc,assignment]
    try:
        _summary, rows = build_business_seller_report(db)
    finally:
        mod.datetime = original  # type: ignore[misc]

    assert len(rows) == 1
    row = rows[0]
    # published: 10 days, archived: 30 days → avg 20
    assert row.avg_hanging_days == 10.0
    assert row.avg_archived_lifetime_days == 30.0
    assert row.avg_lifetime_days == 20.0
    assert row.avg_lifetime_label == "20 дн."


def test_build_business_seller_listings_detail():
    listings = [
        _listing(id=10, seller_name="ООО Тест", brand="BMW", model="X1", year=2019, price=23000),
        _listing(id=11, seller_name="ООО Тест", status=ListingStatus.archived, price=4000),
        _listing(id=12, seller_name="Другой", status=ListingStatus.published, price=1000),
    ]
    avgs = [
        ListingAvgPrice(
            brand="BMW",
            model="X1",
            year=2019,
            avg_price_byn=20000,
            sample_count=20,
            sample_count_raw=20,
            outliers_removed=0,
            window_days=90,
            window_start=datetime(2025, 12, 1),
            window_end=datetime(2026, 3, 1),
        )
    ]
    db = _db_with_listings_and_avgs(listings, avgs)

    stats, rows = build_business_seller_listings(db, "ООО Тест")
    assert stats is not None
    assert stats.total == 2
    assert stats.archived_sum_byn == 4000
    assert len(rows) == 2
    priced = next(r for r in rows if r.listing.id == 10)
    assert priced.vs_market_pct == 15.0
    assert "выше" in priced.vs_market_label
    assert priced.market_avg_label == "20 000"
    assert priced.lifetime_label.startswith("висит")
