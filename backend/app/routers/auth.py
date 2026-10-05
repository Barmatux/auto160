import hashlib
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from threading import Lock
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.analytics import record_auth_event
from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.email_smtp import EmailSendError, send_verification_email
from app.models import User, UserRole
from app.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
    UserPublic,
)
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_token_revoked,
    revoke_token,
    verify_password,
)
from app.seo import site_base_url

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_RESEND_LIMIT = 5
_RESEND_WINDOW = 3600.0
_resend_lock = Lock()
_resend_buckets: dict[str, deque[float]] = defaultdict(deque)

UNVERIFIED_DETAIL = (
    "Подтвердите email: мы отправили письмо со ссылкой. "
    "Если письма нет — запросите повторную отправку."
)


def _base_username_from_email(email: str) -> str:
    local_part = email.split("@", 1)[0].lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", local_part).strip("_")
    if not normalized:
        normalized = "user"
    return normalized[:60]


def _generate_unique_username(db: Session, email: str) -> str:
    base = _base_username_from_email(email)
    candidate = base
    counter = 1
    while db.query(User.id).filter(func.lower(User.username) == candidate.lower()).first():
        suffix = f"_{counter}"
        candidate = f"{base[: 80 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def _hash_verify_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_email_verification(user: User) -> str:
    raw = secrets.token_urlsafe(32)
    user.email_verify_token_hash = _hash_verify_token(raw)
    user.email_verify_sent_at = datetime.utcnow()
    return raw


def _verification_url(request: Request, raw_token: str) -> str:
    base = site_base_url(request).rstrip("/")
    return f"{base}/api/v1/auth/verify-email?{urlencode({'token': raw_token})}"


def _token_expired(user: User) -> bool:
    if not user.email_verify_sent_at:
        return True
    hours = max(1, int(settings.email_verify_token_hours or 24))
    return user.email_verify_sent_at < datetime.utcnow() - timedelta(hours=hours)


def _require_verified(user: User) -> None:
    if user.email_verified_at is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=UNVERIFIED_DETAIL)


def _check_resend_rate_limit(key: str) -> None:
    now = time.time()
    with _resend_lock:
        bucket = _resend_buckets[key]
        while bucket and now - bucket[0] > _RESEND_WINDOW:
            bucket.popleft()
        if len(bucket) >= _RESEND_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов. Попробуйте позже.",
            )
        bucket.append(now)


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _send_user_verification(request: Request, user: User) -> bool:
    raw = _issue_email_verification(user)
    try:
        send_verification_email(
            to=user.email,
            name=user.name or user.username,
            verify_url=_verification_url(request, raw),
        )
        return True
    except EmailSendError:
        return False


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if payload.role == UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin registration is not allowed")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=_generate_unique_username(db, payload.email),
        email=str(payload.email).strip().lower(),
        name=payload.name,
        role=payload.role,
        password_hash=hash_password(payload.password),
        email_verified_at=None,
    )
    email_sent = _send_user_verification(request, user)
    db.add(user)
    db.commit()
    db.refresh(user)
    record_auth_event(request, user, "register")

    if email_sent:
        message = (
            f"Аккаунт создан. Логин: {user.username}. "
            "Мы отправили письмо со ссылкой для подтверждения email — без этого вход недоступен."
        )
    else:
        message = (
            f"Аккаунт создан. Логин: {user.username}. "
            "Письмо сейчас не удалось отправить — нажмите «Отправить ещё раз» на странице регистрации "
            "или входа после настройки почты."
        )
    return RegisterResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        name=user.name,
        role=user.role,
        email_verified=False,
        email_sent=email_sent,
        message=message,
    )


def _find_user_by_login(db: Session, login: str) -> User | None:
    """Resolve user by username or email (case-insensitive)."""
    value = (login or "").strip()
    if not value:
        return None
    lowered = value.lower()
    user = db.query(User).filter(func.lower(User.username) == lowered).first()
    if user:
        return user
    return db.query(User).filter(func.lower(User.email) == lowered).first()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = _find_user_by_login(db, payload.login)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неправильный логин и(или) пароль. ")

    _require_verified(user)

    access_token = create_access_token(subject=user.email)
    refresh_token = create_refresh_token(subject=user.email)
    record_auth_event(request, user, "login")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/verify-email")
def verify_email(token: str = Query(min_length=10), db: Session = Depends(get_db)):
    token_hash = _hash_verify_token(token.strip())
    user = db.query(User).filter(User.email_verify_token_hash == token_hash).first()
    if not user:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или уже использована")
    if user.email_verified_at is not None:
        return RedirectResponse(url="/login?verified=1", status_code=302)
    if _token_expired(user):
        raise HTTPException(
            status_code=400,
            detail="Срок ссылки истёк. Запросите новое письмо для подтверждения email.",
        )

    user.email_verified_at = datetime.utcnow()
    user.email_verify_token_hash = None
    user.email_verify_sent_at = None
    db.commit()
    return RedirectResponse(url="/login?verified=1", status_code=302)


@router.post("/resend-verification")
def resend_verification(
    payload: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    email = str(payload.email).strip().lower()
    _check_resend_rate_limit(f"ip:{_client_ip(request)}")
    _check_resend_rate_limit(f"email:{email}")

    user = db.query(User).filter(func.lower(User.email) == email).first()
    # Always return generic OK to avoid email enumeration.
    if not user or user.email_verified_at is not None:
        return {"ok": True, "message": "Если аккаунт существует и не подтверждён — письмо отправлено."}

    email_sent = _send_user_verification(request, user)
    db.commit()
    if not email_sent:
        raise HTTPException(
            status_code=503,
            detail="Не удалось отправить письмо. Попробуйте позже или напишите в поддержку.",
        )
    return {"ok": True, "message": "Если аккаунт существует и не подтверждён — письмо отправлено."}


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token type")
    if is_token_revoked(decoded):
        raise HTTPException(status_code=401, detail="Refresh token is revoked")

    email = decoded.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid refresh token subject")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    _require_verified(user)

    revoke_token(payload.refresh_token)
    access_token = create_access_token(subject=user.email)
    refresh_token = create_refresh_token(subject=user.email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=400, detail="Authorization Bearer token is required")

    token = authorization.split(" ", 1)[1].strip()
    token_revoked = revoke_token(token)
    return {
        "message": "Logged out",
        "token_revoked": token_revoked,
        "note": "Current implementation uses in-memory token revoke list.",
    }


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user
