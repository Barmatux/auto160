from app.transmission_labels import (
    TRANSMISSION_SLUG_AUTO,
    TRANSMISSION_SLUG_AUTO_CLASSIC,
    TRANSMISSION_SLUG_CVT,
    TRANSMISSION_SLUG_MANUAL,
    TRANSMISSION_SLUG_ROBOT,
    classify_transmission_slug,
    expand_transmission_filter_slugs,
    normalize_transmission_filter_slug,
    parse_transmission_filter_values,
    transmission_db_values_for_slugs,
    transmission_filter_checked_slugs,
    transmission_filter_display_label,
    transmission_filter_select_value,
    transmission_filter_submit_slugs,
)


def test_classify_transmission_values():
    assert classify_transmission_slug("manual") == TRANSMISSION_SLUG_MANUAL
    assert classify_transmission_slug("механика") == TRANSMISSION_SLUG_MANUAL
    assert classify_transmission_slug("automatic") == TRANSMISSION_SLUG_AUTO_CLASSIC
    assert classify_transmission_slug("автомат") == TRANSMISSION_SLUG_AUTO_CLASSIC
    assert classify_transmission_slug("автоматическая") == TRANSMISSION_SLUG_AUTO_CLASSIC
    assert classify_transmission_slug("dct") == TRANSMISSION_SLUG_ROBOT
    assert classify_transmission_slug("робот") == TRANSMISSION_SLUG_ROBOT
    assert classify_transmission_slug("вариатор") == TRANSMISSION_SLUG_CVT


def test_normalize_filter_slug_aliases():
    assert normalize_transmission_filter_slug("automatic") == TRANSMISSION_SLUG_AUTO_CLASSIC
    assert normalize_transmission_filter_slug("автомат") == TRANSMISSION_SLUG_AUTO_CLASSIC
    assert normalize_transmission_filter_slug("dct") == TRANSMISSION_SLUG_ROBOT
    assert normalize_transmission_filter_slug("механика") == TRANSMISSION_SLUG_MANUAL
    assert normalize_transmission_filter_slug("auto") == TRANSMISSION_SLUG_AUTO


def test_parse_and_expand_transmission_filters():
    assert parse_transmission_filter_values(["auto", "manual", "автомат"]) == [
        TRANSMISSION_SLUG_AUTO,
        TRANSMISSION_SLUG_MANUAL,
        TRANSMISSION_SLUG_AUTO_CLASSIC,
    ]
    assert expand_transmission_filter_slugs([TRANSMISSION_SLUG_AUTO]) == [
        TRANSMISSION_SLUG_AUTO_CLASSIC,
        TRANSMISSION_SLUG_ROBOT,
        TRANSMISSION_SLUG_CVT,
    ]


def test_transmission_db_values_for_slugs():
    raw = ["automatic", "dct", "manual", "автомат", "вариатор", "механика", "робот"]
    assert sorted(transmission_db_values_for_slugs(raw, [TRANSMISSION_SLUG_AUTO])) == sorted(
        ["automatic", "dct", "автомат", "вариатор", "робот"]
    )
    assert transmission_db_values_for_slugs(raw, [TRANSMISSION_SLUG_MANUAL]) == ["manual", "механика"]
    assert transmission_db_values_for_slugs(raw, [TRANSMISSION_SLUG_ROBOT]) == ["dct", "робот"]


def test_transmission_filter_ui_helpers():
    assert transmission_filter_checked_slugs([TRANSMISSION_SLUG_AUTO]) == {
        TRANSMISSION_SLUG_AUTO,
        TRANSMISSION_SLUG_AUTO_CLASSIC,
        TRANSMISSION_SLUG_ROBOT,
        TRANSMISSION_SLUG_CVT,
    }
    assert transmission_filter_display_label([TRANSMISSION_SLUG_AUTO]) == "автомат"
    assert transmission_filter_display_label([TRANSMISSION_SLUG_ROBOT, TRANSMISSION_SLUG_MANUAL]) == "робот, механика"
    assert transmission_filter_submit_slugs(
        [TRANSMISSION_SLUG_AUTO_CLASSIC, TRANSMISSION_SLUG_ROBOT, TRANSMISSION_SLUG_CVT]
    ) == [TRANSMISSION_SLUG_AUTO]
    assert transmission_filter_select_value([TRANSMISSION_SLUG_AUTO]) == TRANSMISSION_SLUG_AUTO
    assert transmission_filter_select_value([TRANSMISSION_SLUG_ROBOT]) == TRANSMISSION_SLUG_ROBOT
    assert transmission_filter_select_value([]) == ""
