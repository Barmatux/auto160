from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.analytics import SESSION_COOKIE, SESSION_MAX_AGE, ensure_session_id, record_page_view, should_track_request
from app.telegram_hits import classify_user_agent, note_hit

_BOT_UA_MARKERS = (
    "bot",
    "crawl",
    "spider",
    "slurp",
    "preview",
    "telegram",
    "facebook",
    "whatsapp",
    "discord",
    "linkedin",
    "twitter",
    "embedly",
    "quora",
    "pinterest",
    "skype",
    "vkshare",
    "w3c_validator",
    "wget",
    "curl",
    "python-urllib",
    "httpclient",
    "libwww",
)


def _is_preview_bot(request: Request) -> bool:
    ua = (request.headers.get("user-agent") or "").lower()
    return any(marker in ua for marker in _BOT_UA_MARKERS)


def _looks_like_browser(request: Request) -> bool:
    if _is_preview_bot(request):
        return False
    ua = request.headers.get("user-agent") or ""
    accept = (request.headers.get("accept") or "").lower()
    if "mozilla" not in ua.lower():
        return False
    return "text/html" in accept or "*/*" in accept


def _skip_session_cookie(request: Request) -> bool:
    path = request.url.path
    if path.startswith(("/static/", "/media/", "/favicon.ico", "/robots.txt", "/sitemap.xml", "/og-check", "/health")):
        return True
    return not _looks_like_browser(request)


class AnalyticsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        ua = request.headers.get("user-agent")
        kind = classify_user_agent(ua)
        path = request.url.path
        if kind or path.startswith("/og-check"):
            forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
            ip = forwarded or (request.client.host if request.client else None)
            note_hit(
                path=path,
                method=request.method,
                ip=ip,
                user_agent=ua,
                kind=kind or "og-check",
            )

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
