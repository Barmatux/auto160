from types import SimpleNamespace

from app.util_sbor_exclusions import (
    catalog_item_is_mercedes_16_diesel_160_util_exclusion,
    catalog_payload_is_mercedes_16_diesel_160_util_exclusion,
    is_mercedes_16_diesel_160_util_exclusion,
    listing_is_mercedes_16_diesel_160_util_exclusion,
    listing_payload_is_mercedes_16_diesel_160_util_exclusion,
)


def test_mercedes_16_diesel_160_matches_util_exclusion():
    assert (
        is_mercedes_16_diesel_160_util_exclusion(
            make="Mercedes-Benz",
            fuel_type="дизель",
            engine_volume_l=1.6,
            engine_power_hp=160,
            year=2016,
        )
        is True
    )
    assert (
        is_mercedes_16_diesel_160_util_exclusion(
            make="Mercedes",
            engine_type="Дизель",
            engine_capacity_l=1.6,
            engine_power_hp=160,
            year=2020,
        )
        is True
    )


def test_mercedes_16_diesel_160_rejects_non_matches():
    assert (
        is_mercedes_16_diesel_160_util_exclusion(
            make="Mercedes-Benz",
            fuel_type="дизель",
            engine_volume_l=1.6,
            engine_power_hp=160,
            year=2015,
        )
        is False
    )
    assert (
        is_mercedes_16_diesel_160_util_exclusion(
            make="Mercedes-Benz",
            fuel_type="бензин",
            engine_volume_l=1.6,
            engine_power_hp=160,
            year=2018,
        )
        is False
    )
    assert (
        is_mercedes_16_diesel_160_util_exclusion(
            make="BMW",
            fuel_type="дизель",
            engine_volume_l=1.6,
            engine_power_hp=160,
            year=2018,
        )
        is False
    )
    assert (
        is_mercedes_16_diesel_160_util_exclusion(
            make="Mercedes-Benz",
            fuel_type="дизель",
            engine_volume_l=2.0,
            engine_power_hp=160,
            year=2018,
        )
        is False
    )
    assert (
        is_mercedes_16_diesel_160_util_exclusion(
            make="Mercedes-Benz",
            fuel_type="дизель",
            engine_volume_l=1.6,
            engine_power_hp=150,
            year=2018,
        )
        is False
    )


def test_catalog_year_window_for_util_exclusion():
    assert (
        catalog_item_is_mercedes_16_diesel_160_util_exclusion(
            SimpleNamespace(
                make="Mercedes-Benz",
                fuel_type="дизель",
                engine_volume_l=1.6,
                engine_power_hp=160,
                year_from=2012,
                year_to=2015,
            )
        )
        is False
    )
    assert (
        catalog_item_is_mercedes_16_diesel_160_util_exclusion(
            SimpleNamespace(
                make="Mercedes-Benz",
                fuel_type="дизель",
                engine_volume_l=1.6,
                engine_power_hp=160,
                year_from=2014,
                year_to=2018,
            )
        )
        is True
    )


def test_listing_and_payload_helpers():
    listing = SimpleNamespace(
        brand="Mercedes-Benz",
        engine_type="дизель",
        engine_capacity_l=1.6,
        engine_power_hp=160,
        year=2017,
    )
    assert listing_is_mercedes_16_diesel_160_util_exclusion(listing) is True
    assert (
        listing_payload_is_mercedes_16_diesel_160_util_exclusion(
            {
                "brand": "Mercedes-Benz",
                "engine_type": "дизель",
                "engine_capacity_l": 1.6,
                "engine_power_hp": 160,
                "year": 2017,
            }
        )
        is True
    )
    assert (
        catalog_payload_is_mercedes_16_diesel_160_util_exclusion(
            {
                "make": "Mercedes-Benz",
                "fuel_type": "дизель",
                "engine_volume_l": 1.6,
                "engine_power_hp": 160,
                "year_from": 2016,
                "year_to": 2019,
            }
        )
        is True
    )
