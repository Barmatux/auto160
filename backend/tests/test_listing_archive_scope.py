"""Tests for archived listing catalog scope classification."""

from app.listing_archive_scope import (
    ARCHIVE_REASON_NON_CATALOG,
    ARCHIVE_REASON_OTHER,
    ARCHIVE_REASON_WRONG_GENERATION,
    classify_listing_catalog_scope,
    normalize_catalog_match_name,
)


def test_normalize_catalog_match_name():
    assert normalize_catalog_match_name("Opel  Zafira") == "opel zafira"


def test_classify_non_catalog_model():
    brand_models = {"opel": {"astra"}}
    generation_index = {("opel", "astra"): (frozenset({"K"}), False)}
    reason = classify_listing_catalog_scope(
        brand="Opel",
        model="Zafira",
        generation="B",
        brand_models=brand_models,
        generation_index=generation_index,
    )
    assert reason == ARCHIVE_REASON_NON_CATALOG


def test_classify_wrong_generation():
    brand_models = {"opel": {"zafira"}}
    generation_index = {("opel", "zafira"): (frozenset({"C", "C · Рестайлинг"}), False)}
    reason = classify_listing_catalog_scope(
        brand="Opel",
        model="Zafira",
        generation="B · Рестайлинг",
        brand_models=brand_models,
        generation_index=generation_index,
    )
    assert reason == ARCHIVE_REASON_WRONG_GENERATION


def test_classify_matching_generation_is_other_bucket():
    brand_models = {"opel": {"zafira"}}
    generation_index = {("opel", "zafira"): (frozenset({"C · Рестайлинг"}), False)}
    reason = classify_listing_catalog_scope(
        brand="Opel",
        model="Zafira",
        generation="C · Рестайлинг",
        brand_models=brand_models,
        generation_index=generation_index,
    )
    assert reason == ARCHIVE_REASON_OTHER
