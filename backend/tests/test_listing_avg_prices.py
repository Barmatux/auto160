from datetime import datetime, timedelta

from app.listing_avg_prices import _canonical_brand, _money, recompute_listing_avg_prices


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


def test_recompute_groups_by_brand_model_year():
    now = datetime(2026, 9, 8, 12, 0, 0)
    rows = [
        ("BMW", "3 серия", 2015, 20000),
        ("bmw", "3 series", 2015, 22000),
        ("BMW", "3 серия", 2016, 25000),
        ("Audi", "A4", 2015, 18000),
    ]
    db = _FakeDb(rows)
    stats = recompute_listing_avg_prices(db, window_days=90, now=now)
    assert stats.listings_scanned == 4
    assert stats.rows_written == 3
    assert db.committed is True

    bmw_2015 = next(r for r in db.added if r.year == 2015 and "bmw" in r.brand.lower())
    assert float(bmw_2015.avg_price_byn) == 21000.0
    assert bmw_2015.sample_count == 2
    assert float(bmw_2015.min_price_byn) == 20000.0
    assert float(bmw_2015.max_price_byn) == 22000.0
    assert bmw_2015.window_days == 90
    assert bmw_2015.window_start == now - timedelta(days=90)
