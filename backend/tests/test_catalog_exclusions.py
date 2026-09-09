from app.catalog_exclusions import is_excluded_make_model


def test_toyota_prius_variants_are_excluded():
    assert is_excluded_make_model("Toyota", "Prius")
    assert is_excluded_make_model("Toyota", "Prius C")
    assert is_excluded_make_model("Toyota", "Prius Prime")
    assert is_excluded_make_model("Toyota", "Prius V Plus")


def test_other_models_are_not_excluded():
    assert not is_excluded_make_model("Toyota", "Camry")
    assert not is_excluded_make_model("Volkswagen", "Golf")
