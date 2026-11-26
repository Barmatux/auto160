from app.bca_admin import corrected_mileage, country_label, fuel_label


def test_corrected_mileage_drops_trailing_decimal_zero():
    assert corrected_mileage(1463080) == 146308
    assert corrected_mileage(25812) == 25812
    assert corrected_mileage(None) is None


def test_country_and_fuel_labels():
    assert country_label("DE") == "Германия (DE)"
    assert fuel_label("BEV - battery electric vehicle  100% electric") == "Электро"
    assert fuel_label("Diesel") == "Дизель"
    assert fuel_label("Benzyna") == "Бензин"
