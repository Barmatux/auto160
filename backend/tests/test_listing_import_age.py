from datetime import date

from app.listing_import_age import (
    IMPORT_AGE_OVER_10M,
    IMPORT_AGE_RF_PASSABLE,
    add_calendar_months,
    format_import_date_label,
    import_age_min_months,
    normalize_import_age_filter,
    parse_import_age_filters,
    release_date_matches_import_age,
    release_date_older_than_months,
)


def test_parse_import_age_filters_allows_both():
    both = parse_import_age_filters(True, True)
    assert both.rf_passable is True
    assert both.months_10_12 is True
    assert both.active is True
    assert parse_import_age_filters(False, True).months_10_12 is True
    assert parse_import_age_filters(False, False).active is False


def test_normalize_import_age_filter_reports_combined():
    assert normalize_import_age_filter(True, True) == "both"
    assert normalize_import_age_filter(True, False) == IMPORT_AGE_RF_PASSABLE
    assert normalize_import_age_filter(False, True) == IMPORT_AGE_OVER_10M
    assert normalize_import_age_filter(False, False) is None
    assert import_age_min_months(IMPORT_AGE_RF_PASSABLE) == 12
    assert import_age_min_months(IMPORT_AGE_OVER_10M) == 10
    assert import_age_min_months("both") == 10


def test_release_date_matches_import_age_windows():
    today = date(2026, 9, 23)
    rf_only = parse_import_age_filters(True, False)
    window_only = parse_import_age_filters(False, True)
    both = parse_import_age_filters(True, True)

    # Exactly 12 months -> RF passable, not 10-12 window
    assert release_date_matches_import_age("23.09.2025", rf_only, today=today) is True
    assert release_date_matches_import_age("23.09.2025", window_only, today=today) is False

    # 11 months -> 10-12 window only
    assert release_date_matches_import_age("23.10.2025", window_only, today=today) is True
    assert release_date_matches_import_age("23.10.2025", rf_only, today=today) is False
    assert release_date_matches_import_age("23.10.2025", both, today=today) is True

    # Exactly 10 months -> included in 10-12 window
    assert release_date_matches_import_age("23.11.2025", window_only, today=today) is True

    # Under 10 months -> none
    assert release_date_matches_import_age("24.11.2025", window_only, today=today) is False
    assert release_date_matches_import_age("24.11.2025", both, today=today) is False


def test_release_date_older_than_months():
    today = date(2026, 9, 23)
    assert release_date_older_than_months("23.09.2025", 12, today=today) is True
    assert release_date_older_than_months("24.09.2025", 12, today=today) is False
    assert release_date_older_than_months("23.11.2025", 10, today=today) is True
    assert release_date_older_than_months("24.11.2025", 10, today=today) is False
    assert release_date_older_than_months(None, 10, today=today) is False


def test_add_calendar_months_handles_month_end():
    assert add_calendar_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_calendar_months(date(2026, 9, 23), -12) == date(2025, 9, 23)


def test_format_import_date_label():
    assert format_import_date_label("15.03.2023") == "Дата ввоза в РБ 15.03.2023г."
    assert format_import_date_label("15.03.2023г.") == "Дата ввоза в РБ 15.03.2023г."
    assert format_import_date_label(None) is None
