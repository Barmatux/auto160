from datetime import date

from app.vin_analytics import VinListingSort, parse_filter_date


def test_parse_filter_date_formats():
    assert parse_filter_date("2024-11-26") == date(2024, 11, 26)
    assert parse_filter_date("26.11.2024") == date(2024, 11, 26)
    assert parse_filter_date("26/11/2024") == date(2024, 11, 26)
    assert parse_filter_date(" 05.03.2026 extra") == date(2026, 3, 5)
    assert parse_filter_date("") is None
    assert parse_filter_date("not-a-date") is None


def test_vin_sort_toggle_and_query_string():
    sort = VinListingSort(sort="dates", direction="desc")
    assert sort.query_string() == "tab=vin"
    assert "sort=auto" in sort.toggle_url("auto")
    assert "dir=asc" in sort.toggle_url("auto")
    assert sort.arrow("dates") == "↓"
    assert sort.arrow("auto") == "↕"

    toggled = VinListingSort(sort="import", direction="desc")
    assert "dir=asc" in toggled.toggle_url("import")
    assert toggled.arrow("import") == "↓"
    assert "page=2" in toggled.query_string(page=2)
