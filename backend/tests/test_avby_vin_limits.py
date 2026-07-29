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
