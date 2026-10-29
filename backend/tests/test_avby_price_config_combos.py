from app.avby_price_stats import (
    FilterOption,
    iter_config_combos,
)


def test_iter_config_combos_cartesian():
    options = {
        "engine_type": [FilterOption(1, "Бензин"), FilterOption(5, "Дизель")],
        "engine_capacity": [FilterOption(1200, "1,2 л."), FilterOption(1500, "1,5 л.")],
        "transmission_type": [FilterOption(1, "Автомат"), FilterOption(2, "Механика")],
        "drive_type": [FilterOption(1, "Передний")],
    }
    combos = list(iter_config_combos(options))
    assert len(combos) == 8
    assert combos[0].engine_type.label == "Бензин"
    assert combos[0].engine_capacity.id == 1200
    assert combos[-1].engine_type.id == 5
    assert combos[-1].transmission_type.id == 2


def test_iter_config_combos_empty_when_missing_prop():
    options = {
        "engine_type": [FilterOption(1, "Бензин")],
        "engine_capacity": [FilterOption(1200, "1,2 л.")],
        "transmission_type": [FilterOption(1, "Автомат")],
    }
    assert list(iter_config_combos(options)) == []
