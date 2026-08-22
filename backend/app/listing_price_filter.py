"""Price range filter for /listings (RUB display ranges, BYN stored prices)."""

from __future__ import annotations

from dataclasses import dataclass

from app.exchange_rates import NbrbRates, fetch_nbrb_rates
from app.models import CarListing


@dataclass(frozen=True)
class ListingPriceRangeOption:
    slug: str
    label: str
    min_rub: int | None
    max_rub: int | None


LISTING_PRICE_RANGE_OPTIONS: tuple[ListingPriceRangeOption, ...] = (
    ListingPriceRangeOption("up_to_1m", "до 1 000 000 руб.", None, 1_000_000),
    ListingPriceRangeOption("1m_1_25m", "1 000 000 - 1 250 000", 1_000_000, 1_250_000),
    ListingPriceRangeOption("1m25m_1m5m", "1 250 000 - 1 500 000", 1_250_000, 1_500_000),
    ListingPriceRangeOption("1m5m_2m", "1 500 000 - 2 000 000", 1_500_000, 2_000_000),
    ListingPriceRangeOption("2m_2m5m", "2 000 000 - 2 500 000", 2_000_000, 2_500_000),
    ListingPriceRangeOption("2m5m_3m", "2 500 000 - 3 000 000", 2_500_000, 3_000_000),
)

_LISTING_PRICE_RANGE_BY_SLUG = {option.slug: option for option in LISTING_PRICE_RANGE_OPTIONS}


def listing_price_range_options() -> list[dict[str, str]]:
    return [{"slug": option.slug, "label": option.label} for option in LISTING_PRICE_RANGE_OPTIONS]


def parse_listing_price_range(value: str | None) -> str | None:
    slug = (value or "").strip()
    if not slug:
        return None
    return slug if slug in _LISTING_PRICE_RANGE_BY_SLUG else None


def listing_price_range_label(slug: str | None) -> str | None:
    if not slug:
        return None
    option = _LISTING_PRICE_RANGE_BY_SLUG.get(slug)
    return option.label if option else None


def _convert_rub_to_byn(amount_rub: float, rates: NbrbRates) -> float:
    return rates.convert_rub_to_byn(amount_rub)


def listing_price_range_byn_bounds(
    option: ListingPriceRangeOption,
    rates: NbrbRates,
) -> tuple[float | None, float | None]:
    min_byn = _convert_rub_to_byn(option.min_rub, rates) if option.min_rub is not None else None
    max_byn = _convert_rub_to_byn(option.max_rub, rates) if option.max_rub is not None else None
    return min_byn, max_byn


def apply_listings_price_range_filter(query, price_range: str | None, *, rates: NbrbRates | None = None):
    slug = parse_listing_price_range(price_range)
    if not slug:
        return query

    option = _LISTING_PRICE_RANGE_BY_SLUG[slug]
    resolved_rates = rates if rates is not None else fetch_nbrb_rates()
    if not resolved_rates:
        return query.filter(CarListing.id == -1)

    min_byn, max_byn = listing_price_range_byn_bounds(option, resolved_rates)
    query = query.filter(CarListing.price.isnot(None), CarListing.price_byn_missing.is_(False))
    if max_byn is not None:
        query = query.filter(CarListing.price <= max_byn)
    if min_byn is not None:
        query = query.filter(CarListing.price > min_byn)
    return query
