"""SEO helpers and public page regression tests."""

from starlette.requests import Request

from app.seo import (
    INDEXABLE_CITIES,
    build_robots_txt,
    build_seo_context,
    dumps_json_ld,
    home_seo_meta,
    listing_seo_meta,
    listings_feed_seo_meta,
    organization_json_ld,
    render_sitemap_xml,
    site_base_url,
)
from app.models import CarListing, ListingStatus


def _request(path: str, query_string: bytes = b"") -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
        "query_string": query_string,
    }
    return Request(scope)


def test_site_base_url_uses_public_setting(monkeypatch):
    monkeypatch.setattr("app.seo.settings.public_site_url", "https://auto160.by/")
    assert site_base_url(_request("/")) == "https://auto160.by"


def test_home_seo_includes_json_ld(monkeypatch):
    monkeypatch.setattr("app.seo.settings.public_site_url", "https://auto160.by")
    meta = home_seo_meta(_request("/"))
    assert meta.noindex in (None, False)
    types = {block["@type"] for block in meta.json_ld}
    assert "Organization" in types
    assert "WebSite" in types
    ctx = build_seo_context(_request("/"), meta)
    assert ctx["seo_canonical"] == "https://auto160.by/"
    assert ctx["seo_json_ld_script"]
    assert "Organization" in ctx["seo_json_ld_script"]


def test_listings_feed_indexes_minsk_only():
    minsk = listings_feed_seo_meta(city="Минск", page=1, total=12, noisy_filters=False)
    assert minsk.noindex is False
    assert "Минск" in minsk.title
    assert minsk.path and "city=" in minsk.path

    other = listings_feed_seo_meta(city="Орша", page=1, total=3, noisy_filters=False)
    assert other.noindex is True

    filtered = listings_feed_seo_meta(city="Минск", page=1, total=12, noisy_filters=True)
    assert filtered.noindex is True

    paged = listings_feed_seo_meta(page=2, total=40, noisy_filters=False)
    assert paged.noindex is True

    assert "Минск" in INDEXABLE_CITIES


def test_robots_txt_disallows_compare_and_points_sitemap():
    text = build_robots_txt("https://auto160.by")
    assert "Disallow: /catalog/compare" in text
    assert "Disallow: /design-preview" in text
    assert "Sitemap: https://auto160.by/sitemap.xml" in text


def test_render_sitemap_xml_shape():
    xml = render_sitemap_xml([("https://auto160.by/guides/vin", "2026-07-30")])
    assert "<loc>https://auto160.by/guides/vin</loc>" in xml
    assert "<lastmod>2026-07-30</lastmod>" in xml


def test_listing_seo_json_ld_offer():
    listing = CarListing(
        id=42,
        title="Test VW Golf",
        brand="Volkswagen",
        model="Golf",
        year=2018,
        price=1000000,
        mileage=80000,
        city="Минск",
        status=ListingStatus.published,
        seller_name="seller",
        description="desc",
    )
    meta = listing_seo_meta(listing, cover_url="/static/og-default.svg", base="https://auto160.by")
    assert meta.path == "/listings/42"
    assert any(block.get("@type") == "Offer" for block in meta.json_ld)
    assert any(block.get("@type") == "BreadcrumbList" for block in meta.json_ld)
    dumped = dumps_json_ld(meta.json_ld)
    assert "Volkswagen" in dumped


def test_organization_json_ld_url():
    block = organization_json_ld("https://auto160.by")
    assert block["url"] == "https://auto160.by"
