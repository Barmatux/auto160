from app.brand_exclusions import is_excluded_brand


def test_aixam_and_chatenet_are_excluded():
    assert is_excluded_brand("Aixam")
    assert is_excluded_brand("aixam")
    assert is_excluded_brand("Aixam City")
    assert is_excluded_brand("Chatenet")
    assert is_excluded_brand("chatenet")
    assert not is_excluded_brand("Audi")
    assert not is_excluded_brand(None)
    assert not is_excluded_brand("")
