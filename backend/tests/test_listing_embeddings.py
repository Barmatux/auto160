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


def test_local_embed_is_unit_length():
    from app.listing_embeddings import _local_embed_text
    import math

    vec = _local_embed_text("BMW X1 автомат Минск")
    assert len(vec) == 1536
    norm = math.sqrt(sum(v * v for v in vec))
    assert abs(norm - 1.0) < 1e-6
