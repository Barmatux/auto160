"""Long-lived cache headers for versioned /static assets."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Assets are cache-busted with ?v=… query params in templates.
_STATIC_CACHE_CONTROL = "public, max-age=604800, immutable"


class StaticCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path or ""
        if path.startswith("/static/") and response.status_code == 200:
            response.headers["Cache-Control"] = _STATIC_CACHE_CONTROL
        return response
