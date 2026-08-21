"""Official NBRB exchange rates for listing price conversion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

NBRB_RATES_URL = "https://api.nbrb.by/exrates/rates/{currency}?parammode=2"
_CACHE: dict[str, Any] = {"fetched_at": None, "rates": None}


@dataclass(frozen=True)
class NbrbRates:
    rate_date: date
    usd_rate: float
    usd_scale: int
    rub_rate: float
    rub_scale: int

    @property
    def source_label(self) -> str:
        return "НБ РБ"

    def convert_byn_to_usd(self, amount_byn: float) -> float:
        if self.usd_rate <= 0:
            return 0.0
        return amount_byn / self.usd_rate * self.usd_scale

    def convert_byn_to_rub(self, amount_byn: float) -> float:
        if self.rub_rate <= 0:
            return 0.0
        return amount_byn / self.rub_rate * self.rub_scale


def _parse_rate_date(raw: str | None) -> date:
    if not raw:
        return datetime.now(timezone.utc).date()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return datetime.now(timezone.utc).date()


def _fetch_currency_rate(currency: str) -> dict[str, Any]:
    request = Request(
        NBRB_RATES_URL.format(currency=currency),
        headers={"Accept": "application/json", "User-Agent": "Auto160/1.0"},
    )
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"Unexpected NBRB response for {currency}")
    return payload


def fetch_nbrb_rates(*, force_refresh: bool = False) -> NbrbRates | None:
    fetched_at = _CACHE.get("fetched_at")
    cached = _CACHE.get("rates")
    if (
        not force_refresh
        and isinstance(cached, NbrbRates)
        and isinstance(fetched_at, datetime)
        and (datetime.now(timezone.utc) - fetched_at).total_seconds() < 3600
    ):
        return cached

    try:
        usd_payload = _fetch_currency_rate("USD")
        rub_payload = _fetch_currency_rate("RUB")
    except (URLError, ValueError, TypeError, json.JSONDecodeError, KeyError):
        return cached if isinstance(cached, NbrbRates) else None

    rates = NbrbRates(
        rate_date=_parse_rate_date(usd_payload.get("Date") or rub_payload.get("Date")),
        usd_rate=float(usd_payload["Cur_OfficialRate"]),
        usd_scale=int(usd_payload.get("Cur_Scale") or 1),
        rub_rate=float(rub_payload["Cur_OfficialRate"]),
        rub_scale=int(rub_payload.get("Cur_Scale") or 100),
    )
    _CACHE["fetched_at"] = datetime.now(timezone.utc)
    _CACHE["rates"] = rates
    return rates
