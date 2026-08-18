from app.fuel_type_labels import (
    FUEL_GROUP_DIESEL,
    FUEL_GROUP_GAS_PETROL,
    FUEL_GROUP_PETROL,
    classify_fuel_type,
    fuel_type_db_values_for_filter,
    fuel_type_filter_options,
    normalize_fuel_type_label,
)


def test_groups_diesel_aliases():
    for value in ("diesel", "дизель", "Дизель", "дизельное топливо", "ДТ", "dt"):
        assert classify_fuel_type(value) == FUEL_GROUP_DIESEL


def test_groups_petrol_aliases():
    for value in ("petrol", "gasoline", "бензин", "Бензин", "этанол", "АИ-92", "АИ-95"):
        assert classify_fuel_type(value) == FUEL_GROUP_PETROL


def test_groups_gas_petrol_by_gaz_word():
    for value in ("Газ", "газ", "Газ-бензин", "АИ-92 Газ", "бензин газ"):
        assert classify_fuel_type(value) == FUEL_GROUP_GAS_PETROL


def test_keeps_unknown_fuel_types_separate():
    assert classify_fuel_type("гибрид") == "Гибрид"
    assert classify_fuel_type("electric") == "Electric"


def test_filter_options_deduplicate_groups():
    raw = [
        "diesel",
        "дизель",
        "ДТ",
        "petrol",
        "АИ-95",
        "бензин",
        "Газ",
        "этанол",
        "гибрид",
    ]
    assert fuel_type_filter_options(raw) == [
        FUEL_GROUP_PETROL,
        FUEL_GROUP_DIESEL,
        FUEL_GROUP_GAS_PETROL,
        "Гибрид",
    ]


def test_db_values_for_filter_include_all_aliases():
    raw = ["diesel", "дизель", "ДТ", "petrol", "АИ-92", "Газ", "гибрид"]
    assert sorted(fuel_type_db_values_for_filter(raw, FUEL_GROUP_DIESEL)) == ["diesel", "ДТ", "дизель"]
    assert sorted(fuel_type_db_values_for_filter(raw, FUEL_GROUP_PETROL)) == ["petrol", "АИ-92"]
    assert fuel_type_db_values_for_filter(raw, FUEL_GROUP_GAS_PETROL) == ["Газ"]
    assert fuel_type_db_values_for_filter(raw, "Гибрид") == ["гибрид"]


def test_normalize_fuel_type_label_matches_classify():
    assert normalize_fuel_type_label("diesel") == FUEL_GROUP_DIESEL
