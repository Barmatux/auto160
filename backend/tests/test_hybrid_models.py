from app.hybrid_models import (
    HYBRID_TYPE_LABEL,
    PLUGIN_HYBRID_TYPE_LABEL,
    classify_hybrid_engine_type,
)


def test_classify_plugin_hybrid_before_regular_hybrid():
    assert classify_hybrid_engine_type("бензин (гибрид)", "PHEV") == PLUGIN_HYBRID_TYPE_LABEL
    assert classify_hybrid_engine_type("бензин (гибрид)") == HYBRID_TYPE_LABEL
    assert classify_hybrid_engine_type("дизель (гибрид)") == HYBRID_TYPE_LABEL
