"""Reusable av.by auth session for VIN and API calls.

Keeps JWT + refresh token in memory and DB to avoid login/2captcha on every request.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from curl_cffi import requests
from sqlalchemy.orm import Session

from app.avby_accounts import avby_login_identifier, list_vin_accounts_for_keepalive, select_vin_account
from app.models import AvbyServiceAccount

AVBY_BASE = "https://web-api.av.by"
AVBY_PUBLIC_API_KEY = "x6ba5b05f090d4441cd4fac"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
CREDENTIALS_PATH = Path("data/avby_vin_test_credentials.json")
TOKEN_REFRESH_BUFFER = timedelta(minutes=3)
SESSION_KEEPALIVE_REFRESH_WITHIN = timedelta(minutes=15)

_account_locks: dict[int, threading.Lock] = {}
_memory_sessions: dict[int, AvbySession] = {}
_global_lock = threading.Lock()


@dataclass
class AvbySession:
    api_key: str
    token: str
    refresh_token: str
    expires_at: datetime

    def is_valid(self, *, now: datetime | None = None) -> bool:
        current = now or datetime.utcnow()
        return current + TOKEN_REFRESH_BUFFER < self.expires_at


class AvbySessionError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return {}


def _token_expires_at(token: str) -> datetime:
    payload = _decode_jwt_payload(token)
    exp = payload.get("exp")
    if isinstance(exp, (int, float)):
        return datetime.utcfromtimestamp(exp)
    return datetime.utcnow() + timedelta(minutes=25)


def _api_key_from_token(token: str, fallback: str) -> str:
    return str(_decode_jwt_payload(token).get("api_key") or fallback)


def _avby_headers(api_key: str, token: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-device-type": "web.desktop",
        "Origin": "https://av.by",
        "Referer": "https://av.by/",
        "X-Api-Key": api_key,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _load_credentials() -> tuple[str, str]:
    email = (os.environ.get("AVBY_VIN_TEST_EMAIL") or "").strip()
    password = os.environ.get("AVBY_VIN_TEST_PASSWORD") or ""
    if CREDENTIALS_PATH.exists():
        raw = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        email = email or (raw.get("email") or "").strip()
        password = password or (raw.get("password") or "")
    if not email or not password:
        raise AvbySessionError("VIN test account credentials not configured", status_code=503)
    return email, password


def _captcha_api_key() -> str | None:
    for name in ("CAPTCHA_2CAPTCHA_API_KEY", "TWOCAPTCHA_API_KEY", "RUCAPTCHA_API_KEY"):
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None


def _solve_recaptcha(api_key: str) -> str:
    api_base = os.environ.get("CAPTCHA_API_URL", "https://2captcha.com").rstrip("/")
    submit = requests.post(
        f"{api_base}/in.php",
        data={
            "key": api_key,
            "method": "userrecaptcha",
            "googlekey": "6LewiPMbAAAAAGivApIOmNe4pIjnoWgi5gjRdcW2",
            "pageurl": "https://av.by/",
            "invisible": 1,
            "json": 1,
        },
        timeout=30,
    ).json()
    if submit.get("status") != 1:
        raise AvbySessionError(f"2captcha submit failed: {submit}")
    task_id = submit["request"]
    deadline = time.time() + 180
    while time.time() < deadline:
        time.sleep(5)
        poll = requests.get(
            f"{api_base}/res.php",
            params={"key": api_key, "action": "get", "id": task_id, "json": 1},
            timeout=30,
        ).json()
        if poll.get("status") == 1:
            return poll["request"]
        if poll.get("request") != "CAPCHA_NOT_READY":
            raise AvbySessionError(f"2captcha poll failed: {poll}")
    raise AvbySessionError("2captcha timeout", status_code=504)


def _session_from_login_response(data: dict[str, Any], *, fallback_api_key: str) -> AvbySession:
    token = data.get("token") or ""
    refresh_token = data.get("refreshToken") or ""
    if not token or not refresh_token:
        raise AvbySessionError("av.by login response missing token")
    api_key = data.get("apiKey") or _api_key_from_token(token, fallback_api_key)
    return AvbySession(
        api_key=api_key,
        token=token,
        refresh_token=refresh_token,
        expires_at=_token_expires_at(token),
    )


def _login_avby(*, api_key: str, login: str, password: str, captcha_token: str = "") -> AvbySession:
    resp = requests.post(
        f"{AVBY_BASE}/auth/login/sign-in",
        impersonate="chrome124",
        timeout=30,
        headers=_avby_headers(api_key),
        json={
            "login": login,
            "password": password,
            "googleRecaptcha2InvisibleToken": captcha_token,
        },
    )
    if resp.status_code != 200:
        raise AvbySessionError(f"av.by login failed: {resp.status_code} {resp.text[:200]}")
    return _session_from_login_response(resp.json(), fallback_api_key=api_key)


def _refresh_avby_session(session: AvbySession) -> AvbySession:
    resp = requests.post(
        f"{AVBY_BASE}/auth/token/refresh",
        impersonate="chrome124",
        timeout=30,
        headers=_avby_headers(session.api_key),
        json={"refreshToken": session.refresh_token},
    )
    if resp.status_code != 200:
        raise AvbySessionError(f"av.by refresh failed: {resp.status_code} {resp.text[:200]}")
    return _session_from_login_response(resp.json(), fallback_api_key=session.api_key)


def _full_login(account: AvbyServiceAccount | None) -> AvbySession:
    if account and account.avby_password:
        login = avby_login_identifier(account)
        api_key = account.api_key or AVBY_PUBLIC_API_KEY
        password = account.avby_password
    else:
        email, password = _load_credentials()
        login = email
        api_key = AVBY_PUBLIC_API_KEY

    login_variants = [login]
    if account and account.phone and login.startswith("+375"):
        login_variants.append(account.phone)

    last_error: AvbySessionError | None = None
    for candidate in login_variants:
        try:
            return _login_avby(api_key=api_key, login=candidate, password=password)
        except AvbySessionError as err:
            last_error = err

    if last_error:
        captcha_key = _captcha_api_key()
        if captcha_key:
            captcha_token = _solve_recaptcha(captcha_key)
            for candidate in login_variants:
                try:
                    return _login_avby(
                        api_key=api_key,
                        login=candidate,
                        password=password,
                        captcha_token=captcha_token,
                    )
                except AvbySessionError as err:
                    last_error = err
        raise last_error

    raise AvbySessionError("av.by login failed")


def _session_from_account_row(account: AvbyServiceAccount) -> AvbySession | None:
    if not account.auth_token or not account.refresh_token:
        return None
    expires_at = account.auth_token_expires_at or _token_expires_at(account.auth_token)
    return AvbySession(
        api_key=account.api_key or AVBY_PUBLIC_API_KEY,
        token=account.auth_token,
        refresh_token=account.refresh_token,
        expires_at=expires_at,
    )


def _persist_session(db: Session, account: AvbyServiceAccount, session: AvbySession) -> None:
    account.api_key = session.api_key
    account.auth_token = session.token
    account.refresh_token = session.refresh_token
    account.auth_token_expires_at = session.expires_at
    account.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(account)
    _memory_sessions[account.id] = session


def _account_lock(account_id: int) -> threading.Lock:
    with _global_lock:
        if account_id not in _account_locks:
            _account_locks[account_id] = threading.Lock()
        return _account_locks[account_id]


def get_avby_session(db: Session, account: AvbyServiceAccount) -> AvbySession:
    lock = _account_lock(account.id)
    with lock:
        db.expire(account)
        db.refresh(account)
        stored = _session_from_account_row(account)

        cached = _memory_sessions.get(account.id)
        if cached and stored and stored.expires_at > cached.expires_at:
            cached = None
        if cached and cached.is_valid():
            return cached

        if stored and stored.is_valid():
            _memory_sessions[account.id] = stored
            return stored

        if stored and stored.refresh_token:
            try:
                refreshed = _refresh_avby_session(stored)
                _persist_session(db, account, refreshed)
                return refreshed
            except AvbySessionError:
                pass

        session = _full_login(account)
        _persist_session(db, account, session)
        return session


def ensure_avby_session_fresh(
    db: Session,
    account: AvbyServiceAccount,
    *,
    refresh_if_within: timedelta = SESSION_KEEPALIVE_REFRESH_WITHIN,
) -> AvbySession:
    """Refresh JWT proactively before it expires (for session keeper daemon)."""
    lock = _account_lock(account.id)
    with lock:
        db.expire(account)
        db.refresh(account)

        session = _memory_sessions.get(account.id) or _session_from_account_row(account)
        now = datetime.utcnow()
        if session and session.expires_at - now > refresh_if_within:
            _memory_sessions[account.id] = session
            return session

        if session and session.refresh_token:
            try:
                refreshed = _refresh_avby_session(session)
                _persist_session(db, account, refreshed)
                return refreshed
            except AvbySessionError:
                pass

        session = _full_login(account)
        _persist_session(db, account, session)
        return session


def warm_vin_test_session(db_factory) -> None:
    db = db_factory()
    try:
        accounts = list_vin_accounts_for_keepalive(db)
        if not accounts:
            account = select_vin_account(db)
            if account is None:
                return
            accounts = [account]
        for account in accounts:
            try:
                get_avby_session(db, account)
            except Exception:
                pass
    finally:
        db.close()
