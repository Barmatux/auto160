from types import SimpleNamespace

from app.avby_engine_cc import (
    EngineCcResolution,
    pick_best_modification,
    resolve_engine_cc_for_listing,
    resolve_exact_engine_cc_from_offer,
    score_modification_for_listing,
)


SAMPLE_MODS = [
    {
        "id": 42366,
        "name": "1,2 DIG-T MT (115 л.с.)",
        "engineType": {"label": "бензин", "id": 1},
        "gearBoxType": {"label": "механика", "id": 2},
        "driveType": {"label": "передний привод", "id": 1},
    },
    {
        "id": 42368,
        "name": "1,5 dCI MT (110 л.с.)",
        "engineType": {"label": "дизель", "id": 2},
        "gearBoxType": {"label": "механика", "id": 2},
        "driveType": {"label": "передний привод", "id": 1},
    },
    {
        "id": 62813,
        "name": "1,5 dCI MT (115 л.с.)",
        "engineType": {"label": "дизель", "id": 2},
        "gearBoxType": {"label": "механика", "id": 2},
        "driveType": {"label": "передний привод", "id": 1},
    },
]


def test_score_prefers_matching_diesel_110():
    props = {
        "engine_capacity": "1,5",
        "engine_type": "дизель",
        "transmission_type": "механика",
        "drive_type": "передний привод",
        "engine_power": 110,
    }
    scores = {mod["id"]: score_modification_for_listing(mod, props=props) for mod in SAMPLE_MODS}
    assert scores[42368] > scores[42366]
    assert scores[42368] > scores[62813]
    best = pick_best_modification(SAMPLE_MODS, props=props)
    assert best is not None
    assert best["id"] == 42368


def test_resolve_exact_engine_cc_from_offer(monkeypatch):
    advert = {
        "metadata": {"generationId": 4983},
        "properties": [
            {"name": "engine_capacity", "value": "1,5"},
            {"name": "engine_type", "value": "дизель"},
            {"name": "transmission_type", "value": "механика"},
            {"name": "drive_type", "value": "передний привод"},
            {"name": "engine_power", "value": 110},
        ],
    }

    monkeypatch.setattr(
        "app.avby_engine_cc.fetch_generation_modifications",
        lambda generation_id: SAMPLE_MODS,
    )
    monkeypatch.setattr(
        "app.avby_engine_cc.fetch_modification_detail",
        lambda modification_id: {"engineCapacity": "1461 см.куб."},
    )

    result = resolve_exact_engine_cc_from_offer(advert)
    assert result == EngineCcResolution(
        engine_cc=1461,
        approximate=False,
        modification_id=42368,
        source="avby_mod",
    )


def test_resolve_engine_cc_for_listing_uses_catalog_not_live_avby(monkeypatch):
    catalog_item = SimpleNamespace(
        id=77,
        engine_capacity_cc=999,
        raw_specs={"modification_detail": {"engineCapacity": "999 см.куб."}},
    )
    listing = SimpleNamespace(
        id=1,
        brand="Audi",
        model="A1",
        catalog_item_id=77,
        engine_capacity_l=1.0,
        avby_id=12345,
    )

    class FakeDb:
        def get(self, _model, item_id):
            assert item_id == 77
            return catalog_item

    def _boom(*_args, **_kwargs):
        raise AssertionError("live av.by fetch must not be called")

    monkeypatch.setattr("app.avby_engine_cc.fetch_offer_json", _boom)
    monkeypatch.setattr(
        "app.listing_catalog_link.score_listing_catalog_match",
        lambda _listing, _item: 100,
    )

    result = resolve_engine_cc_for_listing(FakeDb(), listing, engine_capacity_l=1.0)
    assert result == EngineCcResolution(engine_cc=999, approximate=False, source="catalog")


def test_resolve_engine_cc_for_listing_falls_back_to_liters(monkeypatch):
    listing = SimpleNamespace(
        id=2,
        brand="Audi",
        model="A1",
        catalog_item_id=None,
        engine_capacity_l=1.0,
        avby_id=None,
    )

    class FakeDb:
        def get(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(
        "app.avby_engine_cc._catalog_candidates_for_listing",
        lambda _db, _listing: [],
    )
    monkeypatch.setattr("app.avby_engine_cc.fetch_offer_json", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()))

    result = resolve_engine_cc_for_listing(FakeDb(), listing)
    assert result == EngineCcResolution(engine_cc=1000, approximate=True, source="liters")
