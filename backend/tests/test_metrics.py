from starlette.requests import Request

from app.metrics import normalize_yandex_metrika_id, yandex_metrika_context


def _request(path: str) -> Request:
    scope = {"type": "http", "method": "GET", "path": path, "headers": []}
    return Request(scope)


def test_normalize_yandex_metrika_id_accepts_digits():
    assert normalize_yandex_metrika_id("12345678") == "12345678"
    assert normalize_yandex_metrika_id(" 987654321 ") == "987654321"


def test_normalize_yandex_metrika_id_rejects_invalid():
    assert normalize_yandex_metrika_id("") is None
    assert normalize_yandex_metrika_id("abc") is None
    assert normalize_yandex_metrika_id("123;alert(1)") is None


def test_yandex_metrika_context_disabled_on_admin(monkeypatch):
    monkeypatch.setattr("app.metrics.settings.yandex_metrika_id", "12345678")
    assert yandex_metrika_context(_request("/admin/analytics")) == {"yandex_metrika_id": None}


def test_yandex_metrika_context_enabled_on_public_page(monkeypatch):
    monkeypatch.setattr("app.metrics.settings.yandex_metrika_id", "12345678")
    assert yandex_metrika_context(_request("/catalog")) == {"yandex_metrika_id": "12345678"}
