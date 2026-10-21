"""Static /static responses get long-lived Cache-Control."""

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.static_cache import StaticCacheMiddleware


def test_static_paths_get_cache_control():
    async def ok(_request):
        return PlainTextResponse("css")

    app = Starlette(routes=[Route("/static/styles.css", ok), Route("/health", ok)])
    app.add_middleware(StaticCacheMiddleware)
    client = TestClient(app)

    static = client.get("/static/styles.css")
    assert static.status_code == 200
    assert static.headers.get("cache-control") == "public, max-age=604800, immutable"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.headers.get("cache-control") != "public, max-age=604800, immutable"
