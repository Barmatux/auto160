"""Best bank buy rates from myfin.by (Minsk) for the design-lab topline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

MYFIN_MINSK_URL = "https://myfin.by/currency/minsk"
_CACHE: dict[str, Any] = {"fetched_at": None, "rates": None}
_CACHE_TTL_SEC = 30 * 60


@dataclass(frozen=True)
class MyfinBuyRates:
    usd_buy: float
    eur_buy: float
    rub100_buy: float
    source_url: str = MYFIN_MINSK_URL
    source_label: str = "myfin.by"

    def format_usd(self) -> str:
        return _fmt(self.usd_buy)

    def format_eur(self) -> str:
        return _fmt(self.eur_buy)

    def format_rub100(self) -> str:
        return _fmt(self.rub100_buy)


def _fmt(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _parse_best_buy_pair(html: str, currency: str) -> float | None:
    """First β value under «Колебания курса {currency}» is bank buy (Сдать)."""
    pattern = (
        rf"Колебания курса {re.escape(currency)}"
        rf"[\s\S]{{0,1200}}?([0-9]+(?:\.[0-9]+)?)\s*β"
    )
    match = re.search(pattern, html)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_rates(html: str) -> MyfinBuyRates | None:
    usd = _parse_best_buy_pair(html, "USD")
    eur = _parse_best_buy_pair(html, "EUR")
    rub = _parse_best_buy_pair(html, "RUB")
    if usd is None or eur is None or rub is None:
        return None
    if usd <= 0 or eur <= 0 or rub <= 0:
        return None
    return MyfinBuyRates(usd_buy=usd, eur_buy=eur, rub100_buy=rub)


def fetch_myfin_buy_rates(*, force_refresh: bool = False) -> MyfinBuyRates | None:
    fetched_at = _CACHE.get("fetched_at")
    cached = _CACHE.get("rates")
    if (
        not force_refresh
        and isinstance(cached, MyfinBuyRates)
        and isinstance(fetched_at, datetime)
        and (datetime.now(timezone.utc) - fetched_at).total_seconds() < _CACHE_TTL_SEC
    ):
        return cached

    try:
        request = Request(
            MYFIN_MINSK_URL,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ru-RU,ru;q=0.9",
                "User-Agent": "Mozilla/5.0 (compatible; Auto160/1.0; +https://auto160.ru)",
            },
        )
        with urlopen(request, timeout=4) as response:
            html = response.read().decode("utf-8", "replace")
        rates = _parse_rates(html)
    except (URLError, TimeoutError, ValueError, TypeError, OSError):
        return cached if isinstance(cached, MyfinBuyRates) else None

    if rates is None:
        return cached if isinstance(cached, MyfinBuyRates) else None

    _CACHE["fetched_at"] = datetime.now(timezone.utc)
    _CACHE["rates"] = rates
    return rates
