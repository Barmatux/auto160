from datetime import date
from unittest.mock import MagicMock

from app.avby_accounts import (
    VIN_TEST_DAILY_LIMIT,
    can_consume_vin_check,
    is_avby_vin_daily_limit_error_message,
    is_avby_vin_daily_limit_response,
    mark_vin_daily_limit_exhausted,
    reset_vin_checks_if_needed,
    vin_checks_remaining,
)
from app.models import AvbyServiceAccount


PAYWALL_BODY = (
    '{"message":"exception.premium_account.paywall.vin",'
    '"context":{"reason":"Вы посмотрели максимум VIN"}}'
)


def test_detects_avby_vin_paywall_response():
    assert is_avby_vin_daily_limit_response(status_code=429, body=PAYWALL_BODY)
    assert not is_avby_vin_daily_limit_response(status_code=429, body='{"message":"too many requests"}')
    assert not is_avby_vin_daily_limit_response(status_code=502, body=PAYWALL_BODY)


def test_detects_paywall_error_message():
    assert is_avby_vin_daily_limit_error_message("HTTP 429 premium_account.paywall.vin")
    assert not is_avby_vin_daily_limit_error_message("auth failed")


def test_mark_vin_daily_limit_exhausted_syncs_counter():
    account = AvbyServiceAccount(
        email="vin-limit@test.local",
        status="confirmed",
        purpose="vin_test",
        is_active=True,
        api_key="test-key",
        daily_vin_limit=VIN_TEST_DAILY_LIMIT,
        vin_checks_today=0,
        vin_checks_day=date.today(),
    )
    db = MagicMock()

    mark_vin_daily_limit_exhausted(db, account, error_message="paywall")

    assert account.vin_checks_today == VIN_TEST_DAILY_LIMIT
    assert vin_checks_remaining(account) == 0
    assert not can_consume_vin_check(account)
    assert account.error_message == "paywall"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(account)


def test_reset_vin_checks_clears_stale_paywall_error():
    account = AvbyServiceAccount(
        email="reset@test.local",
        status="confirmed",
        purpose="vin_test",
        is_active=True,
        api_key="test-key",
        daily_vin_limit=VIN_TEST_DAILY_LIMIT,
        vin_checks_today=VIN_TEST_DAILY_LIMIT,
        vin_checks_day=date(2026, 1, 1),
        error_message="HTTP 429 premium_account.paywall.vin",
    )

    reset_vin_checks_if_needed(account, today=date(2026, 1, 2))

    assert account.vin_checks_today == 0
    assert account.vin_checks_day == date(2026, 1, 2)
    assert account.error_message is None


def test_manual_vin_fetch_allows_inactive_pool(monkeypatch):
    from app import avby_vin
    from app.avby_vin import AvbyVinError, get_or_fetch_listing_vin
    from app.models import CarListing

    inactive = AvbyServiceAccount(
        id=42,
        email="manual@test.local",
        status="phone_verified",
        purpose="vin_test",
        is_active=False,
        api_key="key",
        daily_vin_limit=30,
        vin_checks_today=0,
        vin_checks_day=date.today(),
    )
    listing = CarListing(
        id=1,
        seller_id=1,
        title="t",
        brand="BMW",
        model="3",
        year=2015,
        mileage=1,
        price=1,
        city="Minsk",
        description="d",
        avby_id=999,
        vin=None,
    )

    monkeypatch.setattr(
        avby_vin,
        "list_vin_accounts_for_checks",
        lambda db, require_active=True: [] if require_active else [inactive],
    )
    monkeypatch.setattr(
        avby_vin,
        "select_vin_account",
        lambda db, exclude_ids=None, require_active=True: None if require_active else inactive,
    )
    monkeypatch.setattr(
        avby_vin,
        "get_avby_session",
        lambda db, account, allow_captcha=None: MagicMock(api_key="k", token="t"),
    )
    monkeypatch.setattr(avby_vin, "_fetch_vin_from_avby", lambda *args, **kwargs: "WBATESTVIN123456789")
    monkeypatch.setattr(avby_vin, "consume_vin_check", lambda db, account: True)
    monkeypatch.setattr(avby_vin, "vin_checks_remaining", lambda account: 29)

    db = MagicMock()
    try:
        get_or_fetch_listing_vin(db, listing, allow_inactive=False)
        assert False, "expected no active pool"
    except AvbyVinError as exc:
        assert exc.status_code == 503

    result = get_or_fetch_listing_vin(db, listing, allow_inactive=True)
    assert result.vin == "WBATESTVIN123456789"
    assert result.source == "avby"
    assert listing.vin == "WBATESTVIN123456789"
