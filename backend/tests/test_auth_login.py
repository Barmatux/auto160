"""Email verification helpers and hard login gate."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers.auth import (
    UNVERIFIED_DETAIL,
    _find_user_by_login,
    _hash_verify_token,
    _require_verified,
    _token_expired,
    login,
    verify_email,
)
from app.schemas import LoginRequest


def test_find_user_by_login_matches_username_case_insensitive():
    db = MagicMock()
    user = SimpleNamespace(id=1, username="Seller_One", email="seller@example.com")
    username_query = MagicMock()
    username_query.filter.return_value.first.return_value = user
    db.query.return_value = username_query

    found = _find_user_by_login(db, "  seller_one  ")
    assert found is user
    assert db.query.call_count == 1


def test_find_user_by_login_falls_back_to_email():
    db = MagicMock()
    user = SimpleNamespace(id=2, username="seller_one", email="Seller@Example.com")

    username_query = MagicMock()
    username_query.filter.return_value.first.return_value = None
    email_query = MagicMock()
    email_query.filter.return_value.first.return_value = user
    db.query.side_effect = [username_query, email_query]

    found = _find_user_by_login(db, "seller@example.com")
    assert found is user
    assert db.query.call_count == 2


def test_find_user_by_login_empty_returns_none():
    db = MagicMock()
    assert _find_user_by_login(db, "   ") is None
    db.query.assert_not_called()


def test_hash_verify_token_stable():
    assert _hash_verify_token("abc") == _hash_verify_token("abc")
    assert _hash_verify_token("abc") != _hash_verify_token("abd")
    assert len(_hash_verify_token("abc")) == 64


def test_token_expired_uses_sent_at():
    user = SimpleNamespace(email_verify_sent_at=datetime.utcnow() - timedelta(hours=48))
    assert _token_expired(user) is True
    user.email_verify_sent_at = datetime.utcnow()
    assert _token_expired(user) is False
    user.email_verify_sent_at = None
    assert _token_expired(user) is True


def test_require_verified_blocks_unverified():
    with pytest.raises(HTTPException) as exc:
        _require_verified(SimpleNamespace(email_verified_at=None))
    assert exc.value.status_code == 403
    assert UNVERIFIED_DETAIL in str(exc.value.detail)


def test_require_verified_allows_verified():
    _require_verified(SimpleNamespace(email_verified_at=datetime.utcnow()))


def test_login_blocked_when_email_unverified():
    db = MagicMock()
    user = SimpleNamespace(
        id=1,
        username="u1",
        email="u1@example.com",
        password_hash="hash",
        email_verified_at=None,
    )
    with patch("app.routers.auth._find_user_by_login", return_value=user), patch(
        "app.routers.auth.verify_password", return_value=True
    ):
        with pytest.raises(HTTPException) as exc:
            login(
                LoginRequest(login="u1@example.com", password="secret1"),
                request=MagicMock(),
                db=db,
            )
    assert exc.value.status_code == 403


def test_verify_email_marks_verified_and_redirects():
    db = MagicMock()
    raw = "tokensecretvalue"
    user = SimpleNamespace(
        email_verified_at=None,
        email_verify_token_hash=_hash_verify_token(raw),
        email_verify_sent_at=datetime.utcnow(),
    )
    query = MagicMock()
    query.filter.return_value.first.return_value = user
    db.query.return_value = query

    response = verify_email(token=raw, db=db)
    assert response.status_code == 302
    assert response.headers["location"] == "/login?verified=1"
    assert user.email_verified_at is not None
    assert user.email_verify_token_hash is None
    db.commit.assert_called_once()
