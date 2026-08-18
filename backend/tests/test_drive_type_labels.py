from app.drive_type_labels import normalize_drive_display_label


def test_shortens_front_and_rear_drive_labels():
    assert normalize_drive_display_label("передний привод") == "Передний"
    assert normalize_drive_display_label("задний привод") == "Задний"


def test_collapses_full_drive_variants():
    assert normalize_drive_display_label("постоянный полный привод") == "Полный"
    assert normalize_drive_display_label("подключаемый полный привод") == "Полный"
    assert normalize_drive_display_label("awd") == "Полный"
