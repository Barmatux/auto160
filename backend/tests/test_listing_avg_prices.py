from datetime import datetime, timedelta

from app.listing_avg_prices import (
    _canonical_brand,
    _money,
    recompute_listing_avg_prices,
    trim_price_outliers,
)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def yield_per(self, _n):
        return iter(self._rows)

    def delete(self):
        return 0


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows
        self.added = []
        self.committed = False

    def query(self, *entities):
        if len(entities) == 1 and getattr(entities[0], "__tablename__", None) == "listing_avg_prices":
            return _FakeQuery([])
        return _FakeQuery(self._rows)

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.committed = True


def test_money_rounds_half_up():
    assert str(_money(10.005)) == "10.01"
    assert str(_money(10.004)) == "10.00"


def test_canonical_brand_keeps_short_allcaps():
    assert _canonical_brand("BMW") == "BMW"
    assert _canonical_brand("toyota") == "Toyota"


def test_trim_price_outliers_removes_extremes():
    prices = [10000, 10500, 11000, 10800, 10200, 10700, 50000]
    kept, removed = trim_price_outliers(prices)
    assert removed == 1
    assert 50000 not in kept
    assert len(kept) == 6


def test_trim_price_outliers_keeps_small_samples():
    prices = [10000, 50000, 12000]
    kept, removed = trim_price_outliers(prices)
    assert removed == 0
    assert kept == prices


def test_recompute_writes_multiple_windows_and_requires_min_samples():
    now = datetime(2026, 9, 8, 12, 0, 0)
    # 12 similar prices in last 30d + 1 extreme outlier
    base = now - timedelta(days=10)
    prices = [20000 + i * 100 for i in range(11)] + [90000]
    rows = [("BMW", "3 серия", 2015, price, base) for price in prices]
    # Older observation only in 90d window
    rows.append(("BMW", "3 серия", 2015, 19500, now - timedelta(days=80)))

    db = _FakeDb(rows)
    stats = recompute_listing_avg_prices(
        db,
        windows=(30, 60, 90),
        min_samples=11,
        now=now,
    )
    assert stats.listings_scanned == 13
    assert set(stats.window_days) == {30, 60, 90}
    assert db.committed is True

    by_window = {r.window_days: r for r in db.added if r.year == 2015}
    assert 30 in by_window
    assert 90 in by_window
    assert by_window[30].sample_count == 11  # outlier dropped
    assert by_window[30].outliers_removed == 1
    assert by_window[30].sample_count_raw == 12
    assert float(by_window[30].max_price_byn) < 90000
    assert by_window[90].sample_count_raw == 13


def test_recompute_skips_groups_below_min_samples():
    now = datetime(2026, 9, 8, 12, 0, 0)
    rows = [
        ("Audi", "A4", 2015, 18000, now - timedelta(days=5)),
        ("Audi", "A4", 2015, 19000, now - timedelta(days=5)),
    ]
    db = _FakeDb(rows)
    stats = recompute_listing_avg_prices(db, windows=(30,), min_samples=11, now=now)
    assert stats.rows_written == 0
    assert db.added == []
