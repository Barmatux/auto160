"""Extract listing prices from av.by advert payloads.

Stored and displayed price is always Belarusian rubles (BYN) exactly as on av.by.
Russian rubles and US dollars are derived later via NBRB rates for reference only.
"""

from __future__ import annotations

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
    return _to_float(currency_block.get("amountFiat") or currency_block.get("amount"))


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
