"""Extract listing prices from av.by advert payloads.

Stored and displayed price is always Belarusian rubles (BYN) exactly as on av.by.
Russian rubles and US dollars are derived later via NBRB rates for reference only.
"""

from __future__ import annotations

import re
from typing import Any

from app.exchange_rates import NbrbRates, fetch_nbrb_rates


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _byn_amount(currency_block: dict[str, Any] | None) -> float | None:
    if not isinstance(currency_block, dict):
        return None
    # av.by UI shows integer `amount`; `amountFiat` is an internal precise value with kopecks.
    amount = _to_float(currency_block.get("amount"))
    if amount is not None:
        return float(int(round(amount)))
    return _to_float(currency_block.get("amountFiat"))


def fetch_price_byn_from_avby_public_url(url: str, *, user_agent: str = "Mozilla/5.0") -> float | None:
    """Fetch exact BYN price from a public cars.av.by advert page."""
    from curl_cffi import requests

    page_url = (url or "").strip()
    if not page_url:
        return None
    response = requests.get(
        page_url,
        impersonate="chrome124",
        timeout=30,
        headers={
            "User-Agent": user_agent,
            "Accept-Language": "ru-RU,ru;q=0.9",
        },
    )
    response.raise_for_status()
    match = re.search(
        r'"byn"\s*:\s*\{\s*"currency"\s*:\s*"byn"\s*,\s*"amount"\s*:\s*(\d+(?:\.\d+)?)\s*,\s*"amountFiat"\s*:\s*(\d+(?:\.\d+)?)',
        response.text,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r'"byn"\s*:\s*\{\s*"currency"\s*:\s*"byn"\s*,\s*"amount"\s*:\s*(\d+(?:\.\d+)?)',
            response.text,
            flags=re.IGNORECASE,
        )
        if match:
            amount = _to_float(match.group(1))
            return float(int(round(amount))) if amount is not None else None
        match = re.search(
            r'"byn"\s*:\s*\{\s*"currency"\s*:\s*"byn"\s*,\s*"amountFiat"\s*:\s*(\d+(?:\.\d+)?)',
            response.text,
            flags=re.IGNORECASE,
        )
        if match:
            return _to_float(match.group(1))
        return None
    amount = _to_float(match.group(1))
    if amount is not None:
        return float(int(round(amount)))
    return _to_float(match.group(2))


def extract_price_byn_from_advert(advert: dict[str, Any]) -> float | None:
    """Return BYN price from av.by advert payload, unchanged."""
    price = advert.get("price") or {}
    return _byn_amount(price.get("byn"))


def fix_rub_stored_as_byn(price: float | int | None, rates: NbrbRates | None = None) -> float | None:
    """Correct legacy rows where Russian rubles were saved in the BYN column."""
    if price is None:
        return None
    amount = float(price)
    if amount <= 0:
        return amount

    resolved_rates = rates if rates is not None else fetch_nbrb_rates()
    if not resolved_rates:
        return amount

    implied_usd = resolved_rates.convert_byn_to_usd(amount)
    if implied_usd <= 200_000:
        return amount

    corrected = amount * resolved_rates.rub_rate / resolved_rates.rub_scale
    if corrected <= 0 or resolved_rates.convert_byn_to_usd(corrected) > 200_000:
        return amount
    return corrected
