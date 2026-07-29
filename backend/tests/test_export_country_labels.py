from app.export_country_labels import (
    EXPORT_COUNTRY_BELARUS,
    EXPORT_COUNTRY_FILTER_OPTIONS,
    export_country_for_avby,
    is_belarus_export_country,
)


def test_export_country_filter_options_only_belarus():
    assert EXPORT_COUNTRY_FILTER_OPTIONS == ("Беларусь",)


def test_export_country_for_avby():
    assert export_country_for_avby() == EXPORT_COUNTRY_BELARUS


def test_is_belarus_export_country():
    assert is_belarus_export_country("Беларусь")
    assert is_belarus_export_country("беларусь")
    assert is_belarus_export_country("Belarus")
    assert not is_belarus_export_country("Германия")
    assert not is_belarus_export_country("")
