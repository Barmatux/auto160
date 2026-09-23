from types import SimpleNamespace
from unittest.mock import MagicMock

from app.routers.auth import _find_user_by_login


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
