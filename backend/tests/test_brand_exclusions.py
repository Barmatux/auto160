from app.brand_exclusions import is_excluded_brand


def test_aixam_is_excluded():
    assert is_excluded_brand("Aixam")
    assert is_excluded_brand("aixam")
    assert is_excluded_brand("Aixam City")
    assert not is_excluded_brand("Audi")
    assert not is_excluded_brand(None)
    assert not is_excluded_brand("")
