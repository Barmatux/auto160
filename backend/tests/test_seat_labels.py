from app.seat_labels import (
    has_7_seats_from_raw,
    normalize_seats_raw,
    parse_seat_counts,
    seats_include_count,
    seats_raw_from_specs,
)


def test_parse_seat_counts():
    assert parse_seat_counts(None) == set()
    assert parse_seat_counts("7") == {7}
    assert parse_seat_counts("5, 7") == {5, 7}
    assert parse_seat_counts("5/7/9") == {5, 7, 9}
    assert parse_seat_counts("5,\xa07") == {5, 7}
    assert parse_seat_counts("17") == {17}


def test_seats_include_count():
    assert seats_include_count("7", 7)
    assert seats_include_count("5, 7", 7)
    assert seats_include_count("5/7", 7)
    assert not seats_include_count("5", 7)
    assert not seats_include_count("17", 7)


def test_has_7_seats_from_raw_specs():
    assert has_7_seats_from_raw(raw_specs={"modification_detail": {"numberOfSeats": "5, 7"}})
    assert not has_7_seats_from_raw(raw_specs={"modification_detail": {"numberOfSeats": "5"}})
    assert seats_raw_from_specs({"modification_detail": {"numberOfSeats": " 7 "}}) == "7"
    assert normalize_seats_raw("") is None
