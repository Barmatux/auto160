from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_yandex_webmaster_verification_file():
    response = client.get("/yandex_e0c0f287ce4b46f7.html")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Verification: e0c0f287ce4b46f7" in response.text


def test_yandex_webmaster_verification_missing_file():
    response = client.get("/yandex_missing.html")
    assert response.status_code == 404
