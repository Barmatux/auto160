from types import SimpleNamespace

from app.eu_listing_check import (
    EU_CHECK_APPROVED,
    EU_CHECK_PENDING,
    EU_CHECK_REJECTED,
    apply_eu_check_on_import,
    format_eu_check_reason,
)


def _status_value(status) -> str:
    return getattr(status, "value", status)


def _listing(**kwargs) -> SimpleNamespace:
    listing = SimpleNamespace(
        status="draft",
        eu_check_status=None,
        eu_check_reason=None,
        price_byn_missing=False,
        price=1000,
    )
    for key, value in kwargs.items():
        setattr(listing, key, value)
    return listing


def test_format_eu_check_reason():
    assert "мощности" in format_eu_check_reason("hp_missing")
    assert "объёма" in format_eu_check_reason("engine_l_missing")
    assert "мощности" in format_eu_check_reason("hp_missing,engine_l_missing")


def test_apply_eu_check_queues_pending():
    listing = _listing()
    apply_eu_check_on_import(listing, check_reason="hp_missing", price_missing=False)
    assert listing.eu_check_status == EU_CHECK_PENDING
    assert _status_value(listing.status) == "draft"


def test_apply_eu_check_preserves_approved():
    listing = _listing(eu_check_status=EU_CHECK_APPROVED, status="published")
    apply_eu_check_on_import(listing, check_reason="engine_l_missing", price_missing=False)
    assert listing.eu_check_status == EU_CHECK_APPROVED
    assert _status_value(listing.status) == "published"


def test_apply_eu_check_preserves_rejected():
    listing = _listing(eu_check_status=EU_CHECK_REJECTED, status="archived")
    apply_eu_check_on_import(listing, check_reason="hp_missing", price_missing=False)
    assert listing.eu_check_status == EU_CHECK_REJECTED
    assert _status_value(listing.status) == "archived"


def test_apply_eu_check_clear_pass_clears_state():
    listing = _listing(eu_check_status=EU_CHECK_REJECTED, status="archived")
    apply_eu_check_on_import(listing, check_reason=None, price_missing=False)
    assert listing.eu_check_status is None
    assert listing.eu_check_reason is None
    assert _status_value(listing.status) == "published"
