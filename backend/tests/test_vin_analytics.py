from datetime import date

from app.vin_analytics import VinListingFilters, import_date_in_range, parse_filter_date


def test_parse_filter_date_formats():
    assert parse_filter_date("2024-11-26") == date(2024, 11, 26)
    assert parse_filter_date("26.11.2024") == date(2024, 11, 26)
    assert parse_filter_date("26/11/2024") == date(2024, 11, 26)
    assert parse_filter_date(" 05.03.2026 extra") == date(2026, 3, 5)
    assert parse_filter_date("") is None
    assert parse_filter_date("not-a-date") is None


def test_import_date_in_range():
    start = date(2024, 11, 1)
    end = date(2024, 11, 30)
    assert import_date_in_range("26.11.2024", start, end) is True
    assert import_date_in_range("01.12.2024", start, end) is False
    assert import_date_in_range(None, start, end) is False
    assert import_date_in_range("26.11.2024", None, None) is True


def test_vin_filters_query_string_keeps_tab_and_active_values():
    filters = VinListingFilters(auto="Peugeot", customs="found", import_from="2024-11-01")
    assert filters.active() is True
    query = filters.query_string(page=2)
    assert "tab=vin" in query
    assert "auto=Peugeot" in query
    assert "customs=found" in query
    assert "import_from=2024-11-01" in query
    assert "page=2" in query
    assert VinListingFilters().active() is False
    assert VinListingFilters().query_string() == "tab=vin"
