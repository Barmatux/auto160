from __future__ import annotations

import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.catalog_gaps import enqueue_catalog_gap
from app.catalog_match import (
    CatalogMatchInput,
    catalog_item_public_dict,
    match_catalog_candidates,
)
from app.catalog_visibility import apply_visible_catalog_filter
from app.config import settings
from app.db import get_db
from app.models import CatalogGap, CatalogItem
from app.schemas import (
    CatalogGapBatchRequest,
    CatalogGapBatchResponse,
    CatalogGapOut,
    CatalogItemPublic,
    CatalogMatchCandidateIn,
    CatalogMatchRequest,
    CatalogMatchResponse,
    CatalogMatchResultOut,
)

router = APIRouter(prefix="/api/v1/internal/catalog", tags=["internal-catalog"])


def _parse_allowed_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    raw = (settings.internal_catalog_allowed_ips or "").strip()
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
                detail=f"Invalid INTERNAL_CATALOG_ALLOWED_IPS entry: {token}",
            ) from exc
    return networks


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return ""


def require_internal_catalog_access(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-Api-Key")] = None,
) -> None:
    expected = (settings.internal_catalog_api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal catalog API is not configured",
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client IP not allowed") from exc
    if not any(ip in network for network in networks):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Client IP not allowed")


def _candidate_to_input(row: CatalogMatchCandidateIn) -> CatalogMatchInput:
    return CatalogMatchInput(
        make=row.make,
        model=row.model,
        generation=row.generation,
        year=row.year,
        body_type=row.body_type,
        fuel_type=row.fuel_type,
        engine_power_hp=row.engine_power_hp,
        engine_volume_l=row.engine_volume_l,
        drivetrain=row.drivetrain,
        transmission=row.transmission,
        source_external_id=row.source_external_id,
        external_ref=row.external_ref,
    )


@router.post("/match", response_model=CatalogMatchResponse)
def match_catalog(
    payload: CatalogMatchRequest,
    _: None = Depends(require_internal_catalog_access),
    db: Session = Depends(get_db),
):
    inputs = [_candidate_to_input(row) for row in payload.candidates]
    outcomes = match_catalog_candidates(db, inputs)
    results: list[CatalogMatchResultOut] = []
    gaps_enqueued = 0
    matched = 0
    not_found = 0

    for outcome, candidate in zip(outcomes, inputs, strict=True):
        gap_id: int | None = None
        if outcome.reason == "not_found":
            not_found += 1
            if payload.enqueue_gaps:
                gap = enqueue_catalog_gap(db, candidate, source=payload.source or "eu2")
                gap_id = gap.id
                gaps_enqueued += 1
        else:
            matched += 1
        results.append(
            CatalogMatchResultOut(
                external_ref=outcome.external_ref,
                matched_catalog_item_id=outcome.matched_catalog_item_id,
                match_confidence=outcome.match_confidence,
                reason=outcome.reason,
                make=outcome.make,
                model=outcome.model,
                gap_id=gap_id,
            )
        )

    if gaps_enqueued:
        db.commit()
    return CatalogMatchResponse(
        results=results,
        matched=matched,
        not_found=not_found,
        gaps_enqueued=gaps_enqueued,
    )


@router.get("/items/{item_id}", response_model=CatalogItemPublic)
def get_catalog_item(
    item_id: int,
    _: None = Depends(require_internal_catalog_access),
    db: Session = Depends(get_db),
):
    item = apply_visible_catalog_filter(db.query(CatalogItem).filter(CatalogItem.id == item_id)).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    return CatalogItemPublic(**catalog_item_public_dict(item))


@router.post("/gaps", response_model=CatalogGapBatchResponse)
def report_catalog_gaps(
    payload: CatalogGapBatchRequest,
    _: None = Depends(require_internal_catalog_access),
    db: Session = Depends(get_db),
):
    created_rows: list[CatalogGap] = []
    for row in payload.gaps:
        gap = enqueue_catalog_gap(
            db,
            CatalogMatchInput(
                make=row.make,
                model=row.model,
                generation=row.generation,
                year=row.year,
                body_type=row.body_type,
                fuel_type=row.fuel_type,
                engine_power_hp=row.engine_power_hp,
                engine_volume_l=row.engine_volume_l,
                drivetrain=row.drivetrain,
                transmission=row.transmission,
                source_external_id=row.source_external_id,
                external_ref=row.external_ref,
            ),
            source=payload.source or "eu2",
            notes=row.notes,
        )
        created_rows.append(gap)
    db.commit()
    for gap in created_rows:
        db.refresh(gap)
    return CatalogGapBatchResponse(created=len(created_rows), gaps=created_rows)


@router.get("/gaps", response_model=list[CatalogGapOut])
def list_catalog_gaps(
    status_filter: str = Query(default="open", alias="status"),
    source: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: None = Depends(require_internal_catalog_access),
    db: Session = Depends(get_db),
):
    query = db.query(CatalogGap)
    if status_filter and status_filter != "all":
        query = query.filter(CatalogGap.status == status_filter)
    if source:
        query = query.filter(CatalogGap.source == source)
    return query.order_by(CatalogGap.created_at.desc(), CatalogGap.id.desc()).limit(limit).all()
