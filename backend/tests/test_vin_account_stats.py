from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.listing_enrichment import (
    VinFoundDateFilter,
    build_vin_found_collection_stats_by_account,
    build_vin_found_collection_stats_by_day,
)
from app.vin_account_stats import build_vin_fetch_stats_by_day


def test_build_vin_fetch_stats_by_day_groups_newest_first():
    class FakeQuery:
        def __init__(self):
            self._mode = "fetches"

        def group_by(self, *args, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            return self

        def all(self):
            if self._mode == "accounts":
                return [
                    SimpleNamespace(id=1, email="a@test.com", phone=None, name="A"),
                    SimpleNamespace(id=2, email="b@test.com", phone=None, name="B"),
                ]
            return [
                (1, date(2026, 9, 16), 3),
                (2, date(2026, 9, 16), 1),
                (1, date(2026, 9, 15), 2),
            ]

    db = MagicMock()

    def query(model):
        q = FakeQuery()
        name = getattr(model, "__name__", str(model))
        if "AvbyServiceAccount" in name:
            q._mode = "accounts"
        return q

    db.query.side_effect = query

    import app.vin_account_stats as stats_mod

    original_display = stats_mod.account_display_login
    stats_mod.account_display_login = lambda account: account.email or f"#{account.id}"
    try:
        groups = build_vin_fetch_stats_by_day(db)
    finally:
        stats_mod.account_display_login = original_display

    assert [g["day"] for g in groups] == ["2026-09-16", "2026-09-15"]
    assert groups[0]["total"] == 4


def test_build_vin_found_collection_stats_by_day_uses_listing_check_dates(monkeypatch):
    listing_today = SimpleNamespace(
        id=1,
        vin="WBA11111111111111",
        vin_fetched_at=datetime(2026, 9, 16, 12, 0, 0),
        created_at=datetime(2026, 9, 10, 8, 0, 0),
    )
    listing_older = SimpleNamespace(
        id=2,
        vin="WBA22222222222222",
        vin_fetched_at=datetime(2026, 9, 10, 9, 0, 0),
        created_at=datetime(2026, 9, 9, 8, 0, 0),
    )

    monkeypatch.setattr(
        "app.listing_enrichment.paginate_rating_one_listings_with_vin",
        lambda db, **kwargs: ([listing_today, listing_older], 2),
    )
    monkeypatch.setattr(
        "app.listing_enrichment.build_listing_vin_account_labels",
        lambda db, listings: {1: "+375336125246", 2: "+375291112233"},
    )

    groups = build_vin_found_collection_stats_by_day(
        MagicMock(),
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 16),
    )
    assert [g["day"] for g in groups] == [
        "2026-09-16",
        "2026-09-15",
        "2026-09-14",
        "2026-09-13",
        "2026-09-12",
        "2026-09-11",
        "2026-09-10",
    ]
    assert groups[0]["total"] == 1
    assert groups[0]["accounts"][0]["label"] == "+375336125246"
    assert groups[-1]["total"] == 1
    assert groups[1]["total"] == 0


def test_build_vin_found_collection_stats_by_account_last_30_days(monkeypatch):
    listing_a = SimpleNamespace(
        id=1,
        vin="WBA11111111111111",
        vin_fetched_at=datetime(2026, 9, 20, 12, 0, 0),
        created_at=datetime(2026, 9, 10, 8, 0, 0),
    )
    listing_b = SimpleNamespace(
        id=2,
        vin="WBA22222222222222",
        vin_fetched_at=datetime(2026, 9, 18, 9, 0, 0),
        created_at=datetime(2026, 9, 9, 8, 0, 0),
    )
    listing_c = SimpleNamespace(
        id=3,
        vin="WBA33333333333333",
        vin_fetched_at=datetime(2026, 9, 19, 9, 0, 0),
        created_at=datetime(2026, 9, 9, 8, 0, 0),
    )

    monkeypatch.setattr(
        "app.listing_enrichment.paginate_rating_one_listings_with_vin",
        lambda db, **kwargs: ([listing_a, listing_b, listing_c], 3),
    )
    monkeypatch.setattr(
        "app.listing_enrichment.build_listing_vin_account_labels",
        lambda db, listings: {
            1: "+375336125246",
            2: "+375291112233",
            3: "+375336125246",
        },
    )

    rows = build_vin_found_collection_stats_by_account(
        MagicMock(),
        days=30,
        today=date(2026, 9, 21),
    )
    assert rows == [
        {"label": "+375336125246", "count": 2},
        {"label": "+375291112233", "count": 1},
    ]
