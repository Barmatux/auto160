from fastapi.testclient import TestClient

from app.main import app
from app.routers.pages import _make_logo_url

client = TestClient(app)


def test_make_logo_url_includes_ds_and_jeep():
    assert _make_logo_url("DS") == "/static/logos/ds.svg"
    assert _make_logo_url("Jeep") == "/static/logos/jeep.svg"


def test_catalog_beta_requires_login():
    response = client.get("/catalog/beta", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_catalog_beta_models_requires_login():
    response = client.get("/catalog/beta/models", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_catalog_beta_step_requires_login():
    response = client.get("/catalog/beta/step/3", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"
