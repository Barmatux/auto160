from datetime import datetime

from tools.import_avby_listings import _parse_avby_datetime


def test_parse_avby_datetime_iso_z():
    assert _parse_avby_datetime("2026-09-16T10:15:30.000Z") == datetime(2026, 9, 16, 10, 15, 30)


def test_parse_avby_datetime_invalid():
    assert _parse_avby_datetime(None) is None
    assert _parse_avby_datetime("") is None
    assert _parse_avby_datetime("not-a-date") is None
