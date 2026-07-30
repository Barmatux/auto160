from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.analytics import SESSION_COOKIE, SESSION_MAX_AGE, ensure_session_id, record_page_view, should_track_request

_BOT_UA_MARKERS = (
    "telegrambot",
    "twitterbot",
    "facebookexternalhit",
    "linkedinbot",
    "slackbot",
    "discordbot",
    "whatsapp",
    "preview",
)


def _is_preview_bot(request: Request) -> bool:
    ua = (request.headers.get("user-agent") or "").lower()
    return any(marker in ua for marker in _BOT_UA_MARKERS)


def _skip_session_cookie(request: Request) -> bool:
    path = request.url.path
    if path.startswith(("/static/", "/media/", "/favicon.ico", "/robots.txt", "/sitemap.xml")):
        return True
    return _is_preview_bot(request)


class AnalyticsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        track = should_track_request(request) and not _is_preview_bot(request)
        if _skip_session_cookie(request):
            response = await call_next(request)
            if track:
                record_page_view(request, response.status_code, None)
            return response

        session_id, is_new = ensure_session_id(request)
        response = await call_next(request)
        if is_new:
            response.set_cookie(
                key=SESSION_COOKIE,
                value=session_id,
                max_age=SESSION_MAX_AGE,
                httponly=True,
                samesite="lax",
            )
        if track:
            record_page_view(request, response.status_code, session_id)
        return response
