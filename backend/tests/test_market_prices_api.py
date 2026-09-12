"""Auth and filter helpers for external market prices API."""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import market_prices
from app.routers.market_prices import _filtered_query, _to_out


def test_require_market_key_fails_closed_when_unset(monkeypatch):
    monkeypatch.setattr(market_prices.settings, "market_prices_api_key", "")
    monkeypatch.setattr(market_prices.settings, "market_prices_allowed_ips", "")
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("1.2.3.4", 123)}
    request = Request(scope)
    with pytest.raises(HTTPException) as exc:
        market_prices.require_market_prices_access(request, x_api_key="anything")
    assert exc.value.status_code == 503


def test_require_market_key_rejects_bad_key(monkeypatch):
    monkeypatch.setattr(market_prices.settings, "market_prices_api_key", "secret-mkt")
    monkeypatch.setattr(market_prices.settings, "market_prices_allowed_ips", "")
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("1.2.3.4", 123)}
    request = Request(scope)
    with pytest.raises(HTTPException) as exc:
        market_prices.require_market_prices_access(request, x_api_key="wrong")
    assert exc.value.status_code == 401


def test_require_market_key_accepts_matching_key(monkeypatch):
    monkeypatch.setattr(market_prices.settings, "market_prices_api_key", "secret-mkt")
    monkeypatch.setattr(market_prices.settings, "market_prices_allowed_ips", "")
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("8.8.8.8", 123)}
    request = Request(scope)
    assert market_prices.require_market_prices_access(request, x_api_key="secret-mkt") is None


def test_require_market_key_enforces_ip_allowlist(monkeypatch):
    monkeypatch.setattr(market_prices.settings, "market_prices_api_key", "secret-mkt")
    monkeypatch.setattr(market_prices.settings, "market_prices_allowed_ips", "10.0.0.0/8")
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("8.8.8.8", 123)}
    request = Request(scope)
    with pytest.raises(HTTPException) as exc:
        market_prices.require_market_prices_access(request, x_api_key="secret-mkt")
    assert exc.value.status_code == 403


def test_to_out_maps_fields():
    from datetime import date

    from app.exchange_rates import NbrbRates

    row = SimpleNamespace(
        brand="BMW",
        model="X1",
        year=2015,
        window_days=90,
        avg_price_byn=Decimal("18500.00"),
        min_price_byn=Decimal("12000.00"),
        max_price_byn=Decimal("24000.00"),
        sample_count=14,
        sample_count_raw=16,
        outliers_removed=2,
        window_start=datetime(2026, 6, 1),
        window_end=datetime(2026, 9, 1),
        computed_at=datetime(2026, 9, 1, 12, 0, 0),
    )
    rates = NbrbRates(rate_date=date(2026, 9, 12), usd_rate=3.25, usd_scale=1, rub_rate=3.5, rub_scale=100)
    out = _to_out(row, rates)
    assert out.brand == "BMW"
    assert out.currency == "BYN"
    assert out.window_days == 90
    assert out.sample_count == 14
    assert out.avg_price_usd == Decimal("5692.31")
    assert out.min_price_usd == Decimal("3692.31")
    assert out.max_price_usd == Decimal("7384.62")


def test_to_out_usd_null_without_rates():
    row = SimpleNamespace(
        brand="BMW",
        model="X1",
        year=2015,
        window_days=90,
        avg_price_byn=Decimal("18500.00"),
        min_price_byn=Decimal("12000.00"),
        max_price_byn=Decimal("24000.00"),
        sample_count=14,
        sample_count_raw=16,
        outliers_removed=2,
        window_start=datetime(2026, 6, 1),
        window_end=datetime(2026, 9, 1),
        computed_at=datetime(2026, 9, 1, 12, 0, 0),
    )
    out = _to_out(row, None)
    assert out.avg_price_usd is None
    assert out.min_price_usd is None
    assert out.max_price_usd is None


class _FakeQuery:
    def __init__(self):
        self.filters = []

    def filter(self, *args):
        self.filters.extend(args)
        return self


class _FakeDb:
    def __init__(self):
        self.last_query = None

    def query(self, model):
        self.last_query = _FakeQuery()
        return self.last_query


def test_filtered_query_rejects_bad_window():
    db = _FakeDb()
    with pytest.raises(HTTPException) as exc:
        _filtered_query(db, brand=None, model=None, year=None, window_days=45, min_samples=11)
    assert exc.value.status_code == 422
