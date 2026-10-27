from app.avby_engine_cc import (
    EngineCcResolution,
    pick_best_modification,
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
