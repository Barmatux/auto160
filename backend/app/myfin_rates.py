"""Best bank buy rates from myfin.by, quoted in Russian rubles for the RF site."""

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
    """Raw myfin BYN buy rates + RUB cross-quotes for the RF topline."""

    usd_buy_byn: float
    eur_buy_byn: float
    rub100_buy_byn: float
    source_url: str = MYFIN_MINSK_URL
    source_label: str = "myfin.by"

    @property
    def usd_rub(self) -> float:
        """RUB per 1 USD via myfin cross-rate."""
        return self.usd_buy_byn * 100.0 / self.rub100_buy_byn

    @property
    def eur_rub(self) -> float:
        """RUB per 1 EUR via myfin cross-rate."""
        return self.eur_buy_byn * 100.0 / self.rub100_buy_byn

    @property
    def byn_rub(self) -> float:
        """RUB per 1 BYN via myfin RUB buy rate."""
        return 100.0 / self.rub100_buy_byn

    def format_usd_rub(self) -> str:
        return _fmt_rub(self.usd_rub)

    def format_eur_rub(self) -> str:
        return _fmt_rub(self.eur_rub)

    def format_byn_rub(self) -> str:
        return _fmt_rub(self.byn_rub)


def _fmt_rub(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
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
    return MyfinBuyRates(usd_buy_byn=usd, eur_buy_byn=eur, rub100_buy_byn=rub)


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
