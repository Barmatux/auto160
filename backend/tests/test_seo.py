"""SEO helpers and public page regression tests."""

from starlette.requests import Request

from app.seo import (
    BELARUS_FAQ,
    EUROPE_FAQ,
    INDEXABLE_CITIES,
    belarus_seo_meta,
    europe_feed_seo_meta,
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
    monkeypatch.setattr("app.seo.settings.public_site_url", "https://auto160.ru/")
    assert site_base_url(_request("/")) == "https://auto160.ru"


def test_home_seo_includes_json_ld(monkeypatch):
    monkeypatch.setattr("app.seo.settings.public_site_url", "https://auto160.ru")
    meta = home_seo_meta(_request("/"))
    assert meta.noindex in (None, False)
    types = {block["@type"] for block in meta.json_ld}
    assert "Organization" in types
    assert "WebSite" in types
    ctx = build_seo_context(_request("/"), meta)
    assert ctx["seo_canonical"] == "https://auto160.ru/"
    assert "льготный утильсбор" in meta.title
    assert "Беларуси" in meta.title
    assert len(meta.description) <= 160
    assert not meta.description.endswith("…")
    assert "Европ" in meta.description
    assert ctx["seo_description"] == meta.description
    assert meta.h1 and "под ключ" in meta.h1
    assert ctx["seo_json_ld_script"]
    assert "Organization" in ctx["seo_json_ld_script"]


def test_belarus_landing_seo_matches_visible_offer():
    meta = belarus_seo_meta("https://auto160.ru")
    assert meta.h1 == "Авто из Беларуси под льготный утильсбор"
    assert "Беларуси" in meta.title
    assert len(meta.description) <= 160
    assert not meta.description.endswith("…")
    assert "3 дня" not in meta.description
    types = {block["@type"] for block in meta.json_ld}
    assert "FAQPage" in types
    assert "BreadcrumbList" in types
    questions = meta.json_ld[1]["mainEntity"]
    assert [item["name"] for item in questions] == [question for question, _answer in BELARUS_FAQ]


def test_europe_feed_seo_matches_visible_offer():
    meta = europe_feed_seo_meta("https://auto160.ru")
    assert meta.h1 == "Авто из Европы под льготный утильсбор"
    assert meta.path == "/eu"
    assert meta.noindex is False
    assert len(meta.description) <= 160
    assert "3 дня" not in meta.description
    assert "1.9" in meta.description
    types = {block["@type"] for block in meta.json_ld}
    assert "FAQPage" in types
    filtered = europe_feed_seo_meta("https://auto160.ru", noisy=True)
    assert filtered.noindex is True
    assert "FAQPage" not in {block["@type"] for block in filtered.json_ld}
    paged = europe_feed_seo_meta("https://auto160.ru", page=2)
    assert paged.noindex is True
    assert "стр. 2" in paged.title
    questions = next(block for block in meta.json_ld if block["@type"] == "FAQPage")["mainEntity"]
    assert [item["name"] for item in questions] == [question for question, _answer in EUROPE_FAQ]


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
    text = build_robots_txt("https://auto160.ru")
    assert "Disallow: /catalog/compare" in text
    assert "Disallow: /design-preview" in text
    assert "Sitemap: https://auto160.ru/sitemap.xml" in text
    assert "Host: auto160.ru" in text
    assert "Clean-param:" in text
    assert "yclid" in text


def test_render_sitemap_xml_shape():
    xml = render_sitemap_xml([("https://auto160.ru/guides/vin", "2026-07-30")])
    assert "<loc>https://auto160.ru/guides/vin</loc>" in xml
    assert "<lastmod>2026-07-30</lastmod>" in xml


def test_render_sitemap_index_shape():
    from app.seo import render_sitemap_index

    xml = render_sitemap_index(
        "https://auto160.ru",
        [("static", "2026-09-27"), ("listings", "2026-09-26")],
    )
    assert "<sitemapindex" in xml
    assert "<loc>https://auto160.ru/sitemap-static.xml</loc>" in xml
    assert "<loc>https://auto160.ru/sitemap-listings.xml</loc>" in xml


def test_chunk_entries_splits_over_limit():
    from app.seo import _chunk_entries

    entries = [(f"https://auto160.ru/x/{i}", "2026-09-27") for i in range(5)]
    parts = _chunk_entries(entries, prefix="listings", max_urls=2)
    assert [slug for slug, _ in parts] == ["listings", "listings-2", "listings-3"]
    assert len(parts[0][1]) == 2
    assert len(parts[2][1]) == 1


def test_build_sitemap_entries_resolves_models():
    """Regression: sitemap used CarListing/CatalogItem without importing them."""
    from unittest.mock import MagicMock

    from app.seo import build_sitemap_entries

    db = MagicMock()
    query = MagicMock()
    query.filter.return_value = query
    query.distinct.return_value = query
    query.order_by.return_value = query
    query.all.return_value = []
    query.scalar.return_value = 0
    db.query.return_value = query

    entries = build_sitemap_entries(db, "https://auto160.ru")
    locs = {loc for loc, _lastmod in entries}
    assert "https://auto160.ru/" in locs
    assert "https://auto160.ru/by" in locs
    assert "https://auto160.ru/catalog" in locs


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
    meta = listing_seo_meta(listing, cover_url="/static/og-default.svg", base="https://auto160.ru")
    assert meta.path == "/listings/42"
    assert any(block.get("@type") == "Offer" for block in meta.json_ld)
    assert any(block.get("@type") == "BreadcrumbList" for block in meta.json_ld)
    dumped = dumps_json_ld(meta.json_ld)
    assert "Volkswagen" in dumped


def test_organization_json_ld_url():
    block = organization_json_ld("https://auto160.ru")
    assert block["url"] == "https://auto160.ru"
