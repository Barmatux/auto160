from app.drive_type_labels import drive_type_sql_predicate, normalize_drive_display_label
from app.models import CarListing


def test_shortens_front_and_rear_drive_labels():
    assert normalize_drive_display_label("передний привод") == "Передний"
    assert normalize_drive_display_label("задний привод") == "Задний"


def test_collapses_full_drive_variants():
    assert normalize_drive_display_label("постоянный полный привод") == "Полный"
    assert normalize_drive_display_label("подключаемый полный привод") == "Полный"
    assert normalize_drive_display_label("awd") == "Полный"


def test_drive_type_sql_predicate_for_known_labels():
    assert drive_type_sql_predicate(CarListing.drive_type, None) is None
    assert drive_type_sql_predicate(CarListing.drive_type, "Передний") is not None
    assert drive_type_sql_predicate(CarListing.drive_type, "полный") is not None
