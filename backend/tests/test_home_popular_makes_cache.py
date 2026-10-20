"""Homepage popular-makes / stats cache helpers."""

from app.routers import pages


def test_home_cache_roundtrip(monkeypatch):
    monkeypatch.setattr(pages, "_HOME_BLOCK_CACHE_TTL_SEC", 60.0)
    pages._HOME_STATS_CACHE = None
    pages._HOME_POPULAR_MAKES_CACHE = None

    assert pages._home_cache_get(None) is None

    stored = pages._home_cache_set({"a": 1})
    loaded = pages._home_cache_get(stored)
    assert loaded == {"a": 1}
    loaded["a"] = 2
    assert pages._home_cache_get(stored) == {"a": 1}

    expired = (0.0, ["x"])
    assert pages._home_cache_get(expired) is None
