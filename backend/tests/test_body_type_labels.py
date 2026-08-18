from app.body_type_labels import (
    body_type_db_values_for_filter,
    body_type_filter_options,
    normalize_body_type_label,
)


def test_maps_english_body_types_to_russian():
    assert normalize_body_type_label("sedan") == "Седан"
    assert normalize_body_type_label("hatchback") == "Хэтчбек 5 дв."
    assert normalize_body_type_label("wagon") == "Универсал"
    assert normalize_body_type_label("minivan") == "Минивэн"
    assert normalize_body_type_label("crossover") == "Кроссовер"


def test_capitalizes_russian_body_types():
    assert normalize_body_type_label("седан") == "Седан"
    assert normalize_body_type_label("хэтчбек 5 дв.") == "Хэтчбек 5 дв."
    assert normalize_body_type_label("лифтбек") == "Лифтбек"


def test_filter_options_deduplicate_aliases():
    raw = ["sedan", "седан", "hatchback", "хэтчбек 5 дв."]
    assert body_type_filter_options(raw) == ["Седан", "Хэтчбек 5 дв."]


def test_db_values_for_filter_include_legacy_english():
    raw = ["sedan", "седан", "hatchback", "хэтчбек 5 дв."]
    assert sorted(body_type_db_values_for_filter(raw, "Седан")) == ["sedan", "седан"]
    assert body_type_db_values_for_filter(raw, "Хэтчбек 5 дв.") == ["hatchback", "хэтчбек 5 дв."]


def test_hides_pickup_from_filter_options():
    raw = ["sedan", "pickup", "пикап", "Пикап"]
    assert body_type_filter_options(raw) == ["Седан"]


def test_detects_pickup_body_types():
    from app.body_type_labels import is_hidden_body_type

    for value in ("pickup", "Pickup", "пикап", "Пикап", "Пикап 4 дв."):
        assert is_hidden_body_type(value)
    assert not is_hidden_body_type("седан")
    assert not is_hidden_body_type(None)
