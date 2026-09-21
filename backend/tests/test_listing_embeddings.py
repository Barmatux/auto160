from types import SimpleNamespace

from app.listing_embeddings import build_listing_embed_text, content_hash


def test_build_listing_embed_text_includes_core_fields():
    listing = SimpleNamespace(
        source="av.by",
        brand="BMW",
        model="X1",
        year=2018,
        city="Минск",
        price=25000,
        engine_power_hp=150,
        engine_capacity_l=1.5,
        engine_type="бензин",
        transmission_type="автомат",
        body_type="кроссовер",
        description="Короткое описание",
    )
    text = build_listing_embed_text(listing)
    assert "av.by" in text
    assert "BMW X1 2018" in text
    assert "Минск" in text
    assert "150 hp" in text
    assert "Короткое описание" in text
    assert len(content_hash(text)) == 64
