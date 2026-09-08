from types import SimpleNamespace

from app.catalog_match import CatalogMatchInput, find_best_catalog_match, score_catalog_match
from app.listing_catalog_link import score_listing_catalog_match


def _item(**kwargs):
    defaults = dict(
        id=1,
        make="BMW",
        model="3 серия",
        generation="F30",
        year_from=2012,
        year_to=2015,
        body_type="седан",
        fuel_type="бензин",
        engine_power_hp=136,
        engine_volume_l=1.6,
        drivetrain="задний",
        transmission="автомат",
        source_external_id="av-123",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_score_exact_modification_gets_high_confidence():
    candidate = CatalogMatchInput(
        make="BMW",
        model="3 серия",
        generation="F30",
        year=2014,
        body_type="седан",
        fuel_type="бензин",
        engine_power_hp=136,
        engine_volume_l=1.6,
    )
    score = score_catalog_match(candidate, _item())
    assert score >= 50


def test_find_best_prefers_closer_hp():
    items = [
        _item(id=1, engine_power_hp=184),
        _item(id=2, engine_power_hp=136),
    ]
    candidate = CatalogMatchInput(make="BMW", model="3 серия", year=2014, body_type="седан", engine_power_hp=136)
    best, score = find_best_catalog_match(candidate, items)
    assert best is not None
    assert best.id == 2
    assert score >= 10


def test_listing_score_delegates_to_catalog_match():
    listing = SimpleNamespace(
        brand="BMW",
        model="3 серия",
        generation="F30",
        year=2014,
        body_type="седан",
        engine_type="бензин",
        engine_power_hp=136,
        cover_photo_url=None,
    )
    assert score_listing_catalog_match(listing, _item()) == score_catalog_match(
        CatalogMatchInput(
            make="BMW",
            model="3 серия",
            generation="F30",
            year=2014,
            body_type="седан",
            fuel_type="бензин",
            engine_power_hp=136,
        ),
        _item(),
    )


def test_require_internal_key_fails_closed_when_unset(monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request

    from app.routers import internal_catalog

    monkeypatch.setattr(internal_catalog.settings, "internal_catalog_api_key", "")
    monkeypatch.setattr(internal_catalog.settings, "internal_catalog_allowed_ips", "")
    scope = {"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 123)}
    request = Request(scope)
    try:
        internal_catalog.require_internal_catalog_access(request, x_api_key="anything")
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 503


def test_require_internal_key_accepts_matching_key(monkeypatch):
    from starlette.requests import Request

    from app.routers import internal_catalog

    monkeypatch.setattr(internal_catalog.settings, "internal_catalog_api_key", "secret-eu2")
    monkeypatch.setattr(internal_catalog.settings, "internal_catalog_allowed_ips", "127.0.0.1")
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [],
        "client": ("127.0.0.1", 123),
    }
    request = Request(scope)
    assert internal_catalog.require_internal_catalog_access(request, x_api_key="secret-eu2") is None
