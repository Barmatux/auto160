"""Manager messenger helpers and ownership checks."""

from app.models import MessageThread
from app.routers.messaging import _normalize_name, _normalize_phone, _visitor_owns_thread


def test_normalize_phone_keeps_digits():
    assert _normalize_phone("+375 (29) 111-22-33") == "+375291112233"
    assert _normalize_phone("  8-029-111-22-33  ") == "80291112233"


def test_normalize_name_strips():
    assert _normalize_name("  Иван   Петров ") == "Иван Петров"


def test_visitor_owns_thread_by_guest_token():
    thread = MessageThread(
        listing_id=1,
        user_id=None,
        guest_token="abc",
        contact_name="A",
        contact_phone="12345",
    )
    assert _visitor_owns_thread(thread, user=None, guest_token="abc") is True
    assert _visitor_owns_thread(thread, user=None, guest_token="zzz") is False
    assert _visitor_owns_thread(thread, user=None, guest_token="") is False


def test_visitor_owns_thread_by_user_id():
    class _User:
        id = 42

    thread = MessageThread(
        listing_id=1,
        user_id=42,
        guest_token=None,
        contact_name="A",
        contact_phone="12345",
    )
    assert _visitor_owns_thread(thread, user=_User(), guest_token=None) is True
    assert _visitor_owns_thread(thread, user=None, guest_token="abc") is False
