"""Catalog /makes listing uses SQL aggregation helpers."""

from app.routers import pages


def test_catalog_query_has_make_filters_detects_sidebar_params(monkeypatch):
    class Q(dict):
        def getlist(self, key):
            raw = self.get(key)
            if raw is None:
                return []
            if isinstance(raw, list):
                return raw
            return [raw]

    class Req:
        def __init__(self, params):
            self.query_params = Q(params)

    assert pages._catalog_query_has_make_filters(Req({}), exact_hp=False, with_listings=False) is False
    assert pages._catalog_query_has_make_filters(Req({"year_from": "2018"}), exact_hp=False, with_listings=False) is True
    assert pages._catalog_query_has_make_filters(Req({"body_type": ["sedan"]}), exact_hp=False, with_listings=False) is True
    assert pages._catalog_query_has_make_filters(Req({}), exact_hp=True, with_listings=False) is True
    assert pages._catalog_query_has_make_filters(Req({}), exact_hp=False, with_listings=True) is True


def test_catalog_makes_default_cache_roundtrip(monkeypatch):
    monkeypatch.setattr(pages, "_HOME_BLOCK_CACHE_TTL_SEC", 60.0)
    pages._CATALOG_MAKES_DEFAULT_CACHE = None
    stored = pages._home_cache_set([{"make": "BMW", "count": 3}])
    pages._CATALOG_MAKES_DEFAULT_CACHE = stored
    loaded = pages._home_cache_get(pages._CATALOG_MAKES_DEFAULT_CACHE)
    assert loaded == [{"make": "BMW", "count": 3}]
    loaded[0]["count"] = 99
    assert pages._home_cache_get(pages._CATALOG_MAKES_DEFAULT_CACHE)[0]["count"] == 3
