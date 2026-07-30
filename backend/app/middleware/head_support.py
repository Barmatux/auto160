"""Make HEAD work for HTML GET routes (Telegram crawlers send HEAD first)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# These already handle HEAD correctly (StaticFiles / explicit HEAD routes).
_NATIVE_HEAD_PREFIXES = ("/static/", "/media/")


class HeadRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method != "HEAD":
            return await call_next(request)

        path = request.url.path
        if path.startswith(_NATIVE_HEAD_PREFIXES):
            return await call_next(request)

        # Page routes only advertise GET; Telegram probes with HEAD and aborts on 405.
        request.scope["method"] = "GET"
        response = await call_next(request)

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["content-length"] = "0"
        return Response(status_code=response.status_code, headers=headers, media_type=response.media_type)
