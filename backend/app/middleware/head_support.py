"""Make HEAD work for all GET routes (Telegram crawlers send HEAD first)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class HeadRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method != "HEAD":
            return await call_next(request)

        # FastAPI routes on this app only advertise GET; Telegram probes with HEAD.
        request.scope["method"] = "GET"
        response = await call_next(request)

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["content-length"] = "0"
        return Response(status_code=response.status_code, headers=headers, media_type=response.media_type)
