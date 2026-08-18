from types import SimpleNamespace

from app.routers.pages import (
    _build_modification_table_groups,
    _format_catalog_year_range,
    _modification_power_sort_key,
)


def _item(**kwargs):
    defaults = {
        "id": 1,
        "make": "Audi",
        "model": "A1",
        "generation": "GB",
        "year_from": 2018,
        "year_to": 2024,
        "body_type": "hatchback",
        "fuel_type": "petrol",
        "engine_power_hp": 150,
        "engine_volume_l": 1.5,
        "transmission": "automatic",
        "drivetrain": "fwd",
        "rating": None,
        "raw_specs": {
            "modification": {"name": "35 TFSI S tronic (150 л.с.)"},
            "modification_detail": {
                "engineCapacity": "1500",
                "maxPowerHP": "150",
                "fuel": "АИ-95",
                "gearBoxType": "робот",
                "driveType": "передний привод",
            },
        },
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_format_catalog_year_range():
    assert _format_catalog_year_range(_item(year_from=2018, year_to=2024)) == "2018–2024"
    assert _format_catalog_year_range(_item(year_from=2020, year_to=2020)) == "2020"
    assert _format_catalog_year_range(_item(year_from=None, year_to=None)) == "—"


def test_build_modification_table_groups_by_body_type_and_sorts_by_power():
    hatchback_low = _item(
        id=1,
        body_type="hatchback",
        raw_specs={
            "modification": {"name": "25 TFSI MT (95 л.с.)"},
            "modification_detail": {"maxPowerHP": "95", "fuel": "АИ-95", "gearBoxType": "механика", "driveType": "передний"},
        },
    )
    hatchback_high = _item(
        id=2,
        body_type="hatchback",
        raw_specs={
            "modification": {"name": "35 TFSI S tronic (150 л.с.)"},
            "modification_detail": {"maxPowerHP": "150", "fuel": "АИ-95", "gearBoxType": "робот", "driveType": "передний"},
        },
    )
    sedan = _item(
        id=3,
        body_type="sedan",
        raw_specs={
            "modification": {"name": "30 TFSI (116 л.с.)"},
            "modification_detail": {"maxPowerHP": "116", "fuel": "АИ-95", "gearBoxType": "робот", "driveType": "передний"},
        },
    )

    groups = _build_modification_table_groups([hatchback_low, hatchback_high, sedan])

    assert [group["body_type"] for group in groups] == ["Хэтчбек 5 дв.", "Седан"]
    assert [row["power"] for row in groups[0]["rows"]] == ["150 л.с.", "95 л.с."]
    assert groups[0]["rows"][0]["name"] == "35 TFSI S tronic (150 л.с.)"
    assert groups[0]["rows"][0]["fuel"] == "АИ-95"


def test_modification_power_sort_key():
    assert _modification_power_sort_key({"power": "150 л.с."}) == 150
    assert _modification_power_sort_key({"power": "—"}) == 0
