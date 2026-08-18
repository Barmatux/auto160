from app.fuel_type_labels import (
    FUEL_GROUP_DIESEL,
    FUEL_GROUP_ELECTRIC,
    FUEL_GROUP_GAS_PETROL,
    FUEL_GROUP_HYBRID,
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


def test_groups_hybrids_before_petrol_or_diesel():
    for value in ("гибрид", "Гибрид", "hybrid", "бензин (гибрид)", "дизель (гибрид)", "PHEV"):
        assert classify_fuel_type(value) == FUEL_GROUP_HYBRID
    assert classify_fuel_type("бензин (гибрид)") != FUEL_GROUP_PETROL
    assert classify_fuel_type("дизель (гибрид)") != FUEL_GROUP_DIESEL


def test_groups_electric():
    for value in ("электро", "Электро", "electric"):
        assert classify_fuel_type(value) == FUEL_GROUP_ELECTRIC


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
        "бензин (гибрид)",
        "дизель (гибрид)",
        "электро",
    ]
    assert fuel_type_filter_options(raw) == [
        FUEL_GROUP_PETROL,
        FUEL_GROUP_DIESEL,
        FUEL_GROUP_GAS_PETROL,
        FUEL_GROUP_HYBRID,
        FUEL_GROUP_ELECTRIC,
    ]


def test_db_values_for_filter_include_all_aliases():
    raw = [
        "diesel",
        "дизель",
        "ДТ",
        "petrol",
        "АИ-92",
        "Газ",
        "гибрид",
        "бензин (гибрид)",
        "дизель (гибрид)",
        "электро",
    ]
    assert sorted(fuel_type_db_values_for_filter(raw, FUEL_GROUP_DIESEL)) == ["diesel", "ДТ", "дизель"]
    assert sorted(fuel_type_db_values_for_filter(raw, FUEL_GROUP_PETROL)) == ["petrol", "АИ-92"]
    assert fuel_type_db_values_for_filter(raw, FUEL_GROUP_GAS_PETROL) == ["Газ"]
    assert sorted(fuel_type_db_values_for_filter(raw, FUEL_GROUP_HYBRID)) == [
        "бензин (гибрид)",
        "гибрид",
        "дизель (гибрид)",
    ]
    assert fuel_type_db_values_for_filter(raw, FUEL_GROUP_ELECTRIC) == ["электро"]


def test_normalize_fuel_type_label_matches_classify():
    assert normalize_fuel_type_label("diesel") == FUEL_GROUP_DIESEL
    assert normalize_fuel_type_label("бензин (гибрид)") == FUEL_GROUP_HYBRID
