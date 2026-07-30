from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.analytics import SESSION_COOKIE, SESSION_MAX_AGE, ensure_session_id, record_page_view


class AnalyticsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
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
        record_page_view(request, response.status_code, session_id)
        return response
