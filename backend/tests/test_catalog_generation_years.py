from app.catalog_generation_years import (
    parse_years_from_avby_catalog_url,
    parse_years_from_generation_slug,
)


def test_parse_years_from_generation_slug():
    assert parse_years_from_generation_slug(None) == (None, None)
    assert parse_years_from_generation_slug("8x-2010-2014") == (2010, 2014)
    assert parse_years_from_generation_slug("ii-2019-") == (2019, None)
    assert parse_years_from_generation_slug("i-2018") == (2018, None)
    assert parse_years_from_generation_slug("i-restajling-2015-2021") == (2015, 2021)
    assert parse_years_from_generation_slug("i-restajling-2022") == (2022, None)
    assert parse_years_from_generation_slug("bad-slug") == (None, None)


def test_parse_years_from_avby_catalog_url():
    assert parse_years_from_avby_catalog_url(None) == (None, None)
    assert parse_years_from_avby_catalog_url("https://av.by/catalog/audi_a1_8x-2010-2014#mod-1") == (2010, 2014)
    assert parse_years_from_avby_catalog_url("https://av.by/catalog/peugeot_2008_ii-2019-") == (2019, None)
    assert parse_years_from_avby_catalog_url("https://av.by/catalog/ds_3-crossback_i-2018") == (2018, None)
    assert parse_years_from_avby_catalog_url(
        "https://av.by/catalog/ds_4_i-restajling-2015-2021/modification/123"
    ) == (2015, 2021)
    assert parse_years_from_avby_catalog_url("https://av.by/catalog/modification/123") == (None, None)
