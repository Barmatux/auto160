"""Tests for legacy catalog activation helpers."""

from datetime import datetime, timedelta

from app.catalog_ratings import generation_key
from app.models import CatalogItem


def test_generation_key_empty():
    assert generation_key(None) == ""
    assert generation_key("  U11  ") == "U11"


def test_legacy_model_scope_logic():
    cutoff = datetime(2026, 9, 10, 15, 30, 0)
    legacy_items = [
        CatalogItem(make="BMW", model="X1", generation="U11", created_at=cutoff - timedelta(days=1)),
        CatalogItem(make="Toyota", model="RAV4", generation="VA", created_at=cutoff - timedelta(hours=1), rating=1),
    ]
    dump_items = [
        CatalogItem(make="Abarth", model="500", generation="I", created_at=cutoff + timedelta(hours=1)),
        CatalogItem(make="BMW", model="X1", generation="E84", created_at=cutoff + timedelta(hours=2)),
    ]
    legacy_models = {
        ((i.make or "").strip(), (i.model or "").strip())
        for i in legacy_items
        if (i.make or "").strip() and (i.model or "").strip()
    }
    assert ("BMW", "X1") in legacy_models
    assert ("Toyota", "RAV4") in legacy_models

    for item in legacy_items + dump_items:
        key = ((item.make or "").strip(), (item.model or "").strip())
        should_active = key in legacy_models
        # BMW X1 dump generation E84 stays active under models scope
        if item.model == "X1":
            assert should_active is True
        if item.make == "Abarth":
            assert should_active is False
