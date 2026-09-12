"""External market average prices API (API-key protected)."""

from __future__ import annotations

import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.listing_avg_prices import DEFAULT_MIN_SAMPLES, DEFAULT_WINDOWS
from app.listing_catalog_link import canonical_model_name, normalize_match_text
from app.models import ListingAvgPrice
from app.schemas import MarketAvgPriceListResponse, MarketAvgPriceOut

router = APIRouter(prefix="/api/v1/market", tags=["market"])

ALLOWED_WINDOWS = frozenset(DEFAULT_WINDOWS)


def _parse_allowed_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    raw = (settings.market_prices_allowed_ips or "").strip()
    if not raw:
        return []
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            networks.append(ipaddress.ip_network(token, strict=False))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid MARKET_PRICES_ALLOWED_IPS entry: {token}",
            ) from exc
    return networks


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return ""


def require_market_prices_access(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-Api-Key")] = None,
) -> None:
    expected = (settings.market_prices_api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market prices API is not configured",
        )
    if not x_api_key or x_api_key.strip() != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    networks = _parse_allowed_networks()
    if not networks:
        return
    ip_raw = _client_ip(request)
    try:
        ip = ipaddress.ip_address(ip_raw)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client IP unavailable") from exc
    if not any(ip in network for network in networks):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client IP not allowed")


def _to_out(row: ListingAvgPrice) -> MarketAvgPriceOut:
    return MarketAvgPriceOut(
        brand=row.brand,
        model=row.model,
        year=row.year,
        window_days=row.window_days,
        avg_price_byn=row.avg_price_byn,
        min_price_byn=row.min_price_byn,
        max_price_byn=row.max_price_byn,
        sample_count=row.sample_count,
        sample_count_raw=row.sample_count_raw,
        outliers_removed=row.outliers_removed,
        currency="BYN",
        window_start=row.window_start,
        window_end=row.window_end,
        computed_at=row.computed_at,
    )


def _filtered_query(
    db: Session,
    *,
    brand: str | None,
    model: str | None,
    year: int | None,
    window_days: int | None,
    min_samples: int,
):
    if window_days is not None and window_days not in ALLOWED_WINDOWS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"window_days must be one of {sorted(ALLOWED_WINDOWS)}",
        )

    query = db.query(ListingAvgPrice).filter(ListingAvgPrice.sample_count >= min_samples)
    brand_name = (brand or "").strip()
    model_name = (model or "").strip()
    if brand_name:
        query = query.filter(func.lower(ListingAvgPrice.brand) == normalize_match_text(brand_name))
    if model_name:
        model_canon = canonical_model_name(model_name) or model_name
        query = query.filter(func.lower(ListingAvgPrice.model) == normalize_match_text(model_canon))
    if year is not None:
        query = query.filter(ListingAvgPrice.year == year)
    if window_days is not None:
        query = query.filter(ListingAvgPrice.window_days == window_days)
    return query


@router.get("/avg-prices", response_model=MarketAvgPriceListResponse)
def list_avg_prices(
    _: None = Depends(require_market_prices_access),
    db: Session = Depends(get_db),
    brand: str | None = Query(default=None, max_length=80),
    model: str | None = Query(default=None, max_length=120),
    year: int | None = Query(default=None, ge=1950, le=2100),
    window_days: int | None = Query(default=None, description="30, 60 or 90; omit for all windows"),
    min_samples: int = Query(
        default=DEFAULT_MIN_SAMPLES,
        ge=1,
        le=1000,
        description="Minimum sample_count after outlier trim (default 11 = >10)",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    query = _filtered_query(
        db,
        brand=brand,
        model=model,
        year=year,
        window_days=window_days,
        min_samples=min_samples,
    )
    total = query.count()
    rows = (
        query.order_by(
            ListingAvgPrice.brand.asc(),
            ListingAvgPrice.model.asc(),
            ListingAvgPrice.year.desc(),
            ListingAvgPrice.window_days.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return MarketAvgPriceListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_to_out(row) for row in rows],
    )


@router.get("/avg-prices/lookup", response_model=MarketAvgPriceListResponse)
def lookup_avg_prices(
    _: None = Depends(require_market_prices_access),
    db: Session = Depends(get_db),
    brand: str = Query(min_length=1, max_length=80),
    model: str = Query(min_length=1, max_length=120),
    year: int = Query(ge=1950, le=2100),
    window_days: int | None = Query(default=None, description="30, 60 or 90; omit to return all windows"),
    min_samples: int = Query(default=DEFAULT_MIN_SAMPLES, ge=1, le=1000),
):
    """Lookup averages for one brand/model/year (one window or all of 30/60/90)."""
    query = _filtered_query(
        db,
        brand=brand,
        model=model,
        year=year,
        window_days=window_days,
        min_samples=min_samples,
    )
    rows = query.order_by(ListingAvgPrice.window_days.asc()).all()
    items = [_to_out(row) for row in rows]
    return MarketAvgPriceListResponse(total=len(items), limit=len(items), offset=0, items=items)
