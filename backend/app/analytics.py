"""Site analytics: page views and user actions stored in DB."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Request
from jose import JWTError
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import SiteEvent, User
from app.security import decode_token, is_token_revoked

logger = logging.getLogger(__name__)

SESSION_COOKIE = "auto160_sid"
SESSION_MAX_AGE = 60 * 60 * 24 * 365

SKIP_PATH_PREFIXES = (
    "/static/",
    "/media/",
    "/api/",
    "/health",
    "/favicon.ico",
    "/robots.txt",
    "/sitemap.xml",
)

EVENT_LABELS = {
    "page_view": "Просмотр страницы",
    "login": "Вход",
    "register": "Регистрация",
    "logout": "Выход",
}


def _truncate(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:limit]


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return _truncate(forwarded.split(",")[0].strip(), 45)
    if request.client and request.client.host:
        return _truncate(request.client.host, 45)
    return None


def _resolve_user_from_request(request: Request, db: Session) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_token(token)
    except JWTError:
        return None
    if payload.get("type") != "access" or is_token_revoked(payload):
        return None
    email = payload.get("sub")
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()


def should_track_request(request: Request) -> bool:
    path = request.url.path
    if any(path.startswith(prefix) for prefix in SKIP_PATH_PREFIXES):
        return False
    if request.method not in {"GET", "HEAD"}:
        return False
    accept = (request.headers.get("accept") or "").lower()
    if "text/html" not in accept and "*/*" not in accept:
        return False
    return True


def ensure_session_id(request: Request) -> tuple[str, bool]:
    existing = request.cookies.get(SESSION_COOKIE)
    if existing and len(existing) <= 64:
        return existing, False
    return str(uuid.uuid4()), True


def record_site_event(
    db: Session,
    *,
    event_type: str,
    request: Request,
    user: User | None = None,
    status_code: int | None = None,
    details: dict | None = None,
    session_id: str | None = None,
) -> None:
    sid = session_id or request.cookies.get(SESSION_COOKIE)
    event = SiteEvent(
        event_type=event_type,
        method=request.method[:10],
        path=_truncate(request.url.path, 500) or "/",
        query_string=_truncate(str(request.url.query), 500),
        status_code=status_code,
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        session_id=_truncate(sid, 64),
        ip_address=_client_ip(request),
        user_agent=_truncate(request.headers.get("user-agent"), 500),
        referrer=_truncate(request.headers.get("referer"), 500),
        details=details or None,
        created_at=datetime.now(UTC),
    )
    db.add(event)
    if event_type == "page_view":
        logger.debug(
            "site-event: type=%s path=%s user=%s session=%s ip=%s",
            event_type,
            event.path,
            event.user_email or "-",
            event.session_id or "-",
            event.ip_address or "-",
        )
    else:
        logger.info(
            "site-event: type=%s path=%s user=%s session=%s ip=%s",
            event_type,
            event.path,
            event.user_email or "-",
            event.session_id or "-",
            event.ip_address or "-",
        )


def record_page_view(request: Request, status_code: int, session_id: str | None) -> None:
    if status_code >= 400 or not should_track_request(request):
        return
    db = SessionLocal()
    try:
        user = _resolve_user_from_request(request, db)
        record_site_event(
            db,
            event_type="page_view",
            request=request,
            user=user,
            status_code=status_code,
            session_id=session_id,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("analytics-page-view-failed: path=%s", request.url.path)
    finally:
        db.close()


def record_auth_event(request: Request, user: User, event_type: str) -> None:
    db = SessionLocal()
    try:
        record_site_event(
            db,
            event_type=event_type,
            request=request,
            user=user,
            status_code=200,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("analytics-auth-event-failed: type=%s user_id=%s", event_type, user.id)
    finally:
        db.close()


def _since(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


def build_analytics_summary(db: Session, *, days: int = 7) -> dict:
    since = _since(days)
    since_today = _since(1)

    def count_events(event_type: str | None, period_since: datetime) -> int:
        query = db.query(func.count(SiteEvent.id)).filter(SiteEvent.created_at >= period_since)
        if event_type:
            query = query.filter(SiteEvent.event_type == event_type)
        return int(query.scalar() or 0)

    def unique_sessions(period_since: datetime) -> int:
        value = (
            db.query(func.count(func.distinct(SiteEvent.session_id)))
            .filter(
                SiteEvent.created_at >= period_since,
                SiteEvent.session_id.isnot(None),
                SiteEvent.session_id != "",
            )
            .scalar()
        )
        return int(value or 0)

    top_pages = (
        db.query(SiteEvent.path, func.count(SiteEvent.id).label("views"))
        .filter(SiteEvent.event_type == "page_view", SiteEvent.created_at >= since)
        .group_by(SiteEvent.path)
        .order_by(desc("views"))
        .limit(15)
        .all()
    )

    top_users = (
        db.query(SiteEvent.user_email, func.count(SiteEvent.id).label("events"))
        .filter(
            SiteEvent.created_at >= since,
            SiteEvent.user_email.isnot(None),
        )
        .group_by(SiteEvent.user_email)
        .order_by(desc("events"))
        .limit(10)
        .all()
    )

    recent_events = (
        db.query(SiteEvent)
        .order_by(SiteEvent.created_at.desc())
        .limit(100)
        .all()
    )

    return {
        "days": days,
        "views_today": count_events("page_view", since_today),
        "views_period": count_events("page_view", since),
        "sessions_today": unique_sessions(since_today),
        "sessions_period": unique_sessions(since),
        "actions_period": count_events(None, since) - count_events("page_view", since),
        "top_pages": [{"path": path, "views": views} for path, views in top_pages],
        "top_users": [{"email": email, "events": events} for email, events in top_users],
        "recent_events": recent_events,
        "event_labels": EVENT_LABELS,
        "fetched_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
