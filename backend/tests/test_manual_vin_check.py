import json
import sys
from unittest.mock import MagicMock

# models.py uses Python 3.10+ unions; keep these pure-helper tests runnable on 3.9 CI/local.
sys.modules.setdefault("app.avby_price", MagicMock(extract_price_byn_from_advert=lambda advert: 37333))
sys.modules.setdefault("app.listing_catalog_link", MagicMock())
sys.modules.setdefault("app.listing_enrichment", MagicMock())
sys.modules.setdefault("app.listing_missing_byn", MagicMock())
sys.modules.setdefault("app.models", MagicMock())
sys.modules.setdefault("app.security", MagicMock(hash_password=lambda value: "hash"))

from app.manual_vin_check import (  # noqa: E402
    advert_to_listing_payload,
    extract_advert_from_listing_html,
    extract_initial_value_from_html,
    parse_avby_url,
    parse_filter_query_to_properties,
)


def test_parse_listing_url():
    parsed = parse_avby_url("https://cars.av.by/ford/focus/142105162")
    assert parsed.kind == "listing"
    assert parsed.listing_id == 142105162


def test_parse_filter_url():
    parsed = parse_avby_url(
        "https://cars.av.by/filter?year%5Bmin%5D=2020&price_usd%5Bmin%5D=10000&sort=4"
    )
    assert parsed.kind == "search"
    assert "year" in parsed.filter_query
    assert parsed.page == 1


def test_parse_brand_landing_as_search():
    parsed = parse_avby_url("https://cars.av.by/ford/focus")
    assert parsed.kind == "search"
    assert parsed.listing_id is None


def test_parse_filter_query_to_properties_brands_and_ranges():
    props, sorting = parse_filter_query_to_properties(
        "brands[0][brand]=330&brands[0][model]=349&year[min]=2020&price_currency=2&sort=4"
    )
    assert sorting == 4
    by_name = {item["name"]: item["value"] for item in props}
    assert by_name["brands"] == [{"brand": 330, "model": 349}]
    assert by_name["year"] == {"min": 2020}
    assert by_name["price_currency"] == 2


def test_extract_initial_value_from_html():
    html = (
        ',"filterLoading":false,"initialValue":"brands[0][brand]=330\\u0026brands[0][model]=349'
        '\\u0026price_currency=2","nextPage":2,'
    )
    assert (
        extract_initial_value_from_html(html)
        == "brands[0][brand]=330&brands[0][model]=349&price_currency=2"
    )


def test_extract_advert_from_listing_html_and_payload():
    advert = {
        "id": 142105162,
        "year": 2020,
        "publicUrl": "https://cars.av.by/ford/focus/142105162",
        "shortLocationName": "Слуцк",
        "sellerName": "Test Seller",
        "description": "desc",
        "publishedAt": "2026-03-01T10:00:00+03:00",
        "refreshedAt": "2026-03-10T12:00:00+03:00",
        "price": {"byn": {"currency": "byn", "amount": 37333}},
        "photos": [
            {
                "main": True,
                "big": {"url": "https://example.com/big.jpg"},
                "medium": {"url": "https://example.com/med.jpg"},
            }
        ],
        "metadata": {"title": "Ford Focus 2020", "brandSlug": "ford", "modelSlug": "focus"},
        "properties": [
            {"name": "brand", "value": "Ford"},
            {"name": "model", "value": "Focus"},
            {"name": "mileage_km", "value": 85000},
            {"name": "engine_power", "value": 120},
            {"name": "vin_indicated", "value": True},
        ],
    }
    html = "prefix" + json.dumps(advert, ensure_ascii=False) + "suffix"
    extracted = extract_advert_from_listing_html(html, 142105162)
    assert extracted is not None
    assert extracted["renewedAt"] == advert["refreshedAt"]

    payload = advert_to_listing_payload(extracted)
    assert payload is not None
    assert payload["avby_id"] == 142105162
    assert payload["brand"] == "Ford"
    assert payload["model"] == "Focus"
    assert payload["mileage"] == 85000
    assert payload["price"] == 37333
    assert payload["vin_indicated"] is True
    assert payload["avby_renewed_at"] is not None
