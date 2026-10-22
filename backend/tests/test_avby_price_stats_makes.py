from types import SimpleNamespace

from app.avby_price_stats import years_for_target


def test_years_for_target_open_ended_uses_current_year(monkeypatch):
    monkeypatch.setattr(
        "app.avby_price_stats.datetime",
        SimpleNamespace(utcnow=lambda: SimpleNamespace(year=2026)),
    )
    target = SimpleNamespace(year_from=2019, year_to=None)
    years = years_for_target(target)
    assert years[0] == 2019
    assert years[-1] == 2026
    assert len(years) == 8


def test_years_for_target_typo_year_to_falls_back(monkeypatch):
    monkeypatch.setattr(
        "app.avby_price_stats.datetime",
        SimpleNamespace(utcnow=lambda: SimpleNamespace(year=2026)),
    )
    target = SimpleNamespace(year_from=2014, year_to=1018)
    years = years_for_target(target)
    assert years[0] == 2014
    assert years[-1] == 2026


def test_years_for_target_min_year_clips():
    target = SimpleNamespace(year_from=1995, year_to=2008)
    years = years_for_target(target, min_year=2005)
    assert years == list(range(2005, 2009))


def test_upsert_accepts_arbitrage_track_flag():
    import inspect

    from app.avby_price_stats import build_catalog_generation_rows, upsert_targets_from_catalog

    assert "arbitrage_track_only" in inspect.signature(build_catalog_generation_rows).parameters
    assert "arbitrage_track_only" in inspect.signature(upsert_targets_from_catalog).parameters
