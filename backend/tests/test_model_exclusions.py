from app.model_exclusions import is_excluded_model


def test_prius_variants_are_excluded():
    assert is_excluded_model("Prius")
    assert is_excluded_model("prius")
    assert is_excluded_model("Prius+")
    assert is_excluded_model("Prius C")
    assert is_excluded_model("Prius V(+)")
    assert is_excluded_model("Prius Prime")
    assert is_excluded_model("Prius PHV")
    assert is_excluded_model(None, title="Toyota Prius, 1.8 l., Хэтчбек 2018")


def test_non_prius_models_are_kept():
    assert not is_excluded_model("Corolla")
    assert not is_excluded_model("RAV4")
    assert not is_excluded_model("Yaris Cross")
    assert not is_excluded_model(None)
    assert not is_excluded_model("")
    assert not is_excluded_model(None, title="Toyota Corolla 2020")
