"""Receive the current BCA catalog from the parser."""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.bca_admin import sync_parsed_lots
from app.config import settings
from app.db import get_db

router = APIRouter(prefix="/api/v1/bca", tags=["bca-sync"])
MAX_ITEMS = 8000


class BcaSyncRequest(BaseModel):
    items: list[dict[str, Any]] = Field(default_factory=list)
    replace: bool = True


def require_bca_sync_access(
    x_api_key: Annotated[str | None, Header(alias="X-Api-Key")] = None,
) -> None:
    expected = (settings.bca_sync_api_key or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BCA sync is not configured",
        )
    provided = (x_api_key or "").strip()
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


@router.post("/sync")
def sync_bca_listings(
    payload: BcaSyncRequest,
    _: None = Depends(require_bca_sync_access),
    db: Session = Depends(get_db),
):
    if len(payload.items) > MAX_ITEMS:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Too many listings")
    result = sync_parsed_lots(db, payload.items, replace=payload.replace)
    db.commit()
    return result
