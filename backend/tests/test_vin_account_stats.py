from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

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
        filtered = build_vin_fetch_stats_by_day(
            db,
            date_from=date(2026, 9, 16),
            date_to=date(2026, 9, 16),
        )
    finally:
        stats_mod.account_display_login = original_display

    assert [g["day"] for g in groups] == ["2026-09-16", "2026-09-15"]
    assert groups[0]["day_label"] == "16.09.2026"
    assert groups[0]["total"] == 4
    assert [(a["label"], a["count"]) for a in groups[0]["accounts"]] == [
        ("a@test.com", 3),
        ("b@test.com", 1),
    ]
    assert groups[1]["total"] == 2
    assert isinstance(filtered, list)
