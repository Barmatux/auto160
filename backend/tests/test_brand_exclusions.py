from app.brand_exclusions import is_excluded_brand


def test_aixam_chatenet_microcar_bellier_are_excluded():
    assert is_excluded_brand("Aixam")
    assert is_excluded_brand("aixam")
    assert is_excluded_brand("Aixam City")
    assert is_excluded_brand("Chatenet")
    assert is_excluded_brand("chatenet")
    assert is_excluded_brand("Microcar")
    assert is_excluded_brand("microcar")
    assert is_excluded_brand("Bellier")
    assert is_excluded_brand("bellier")
    assert not is_excluded_brand("Audi")
    assert not is_excluded_brand(None)
    assert not is_excluded_brand("")
