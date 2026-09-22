from app.auto24_map import parse_engine_field


def test_parse_engine_liters_and_kw():
    liters, hp = parse_engine_field("1.5 71kW")
    assert liters == 1.5
    assert hp == 97  # round(71 * 1.35962)


def test_parse_engine_kw_only_no_false_liters():
    liters, hp = parse_engine_field("70kW")
    assert liters is None
    assert hp == 95


def test_parse_engine_from_title():
    liters, hp = parse_engine_field(None, "Ford Focus 1.5 71kW")
    assert liters == 1.5
    assert hp == 97
