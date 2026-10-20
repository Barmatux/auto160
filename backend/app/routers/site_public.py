"""Public endpoints for Belarus landing leads and import-date lookup."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.featured import create_site_lead, lookup_public_import_date
from app.schemas import (
    ImportDateLookupRequest,
    ImportDateLookupResponse,
    SiteLeadCreateRequest,
    SiteLeadOut,
)

router = APIRouter(prefix="/api/v1/public", tags=["public"])


@router.post("/leads", response_model=SiteLeadOut)
def submit_site_lead(payload: SiteLeadCreateRequest, db: Session = Depends(get_db)):
    try:
        return create_site_lead(
            db,
            contact_name=payload.contact_name,
            contact=payload.contact,
            comment=payload.comment,
            listing_id=payload.listing_id,
            avby_url=payload.avby_url,
            source=payload.source or "belarus_landing",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import-date", response_model=ImportDateLookupResponse)
def lookup_import_date(payload: ImportDateLookupRequest, db: Session = Depends(get_db)):
    result = lookup_public_import_date(db, payload.query)
    return ImportDateLookupResponse(
        ok=result.ok,
        input_kind=result.input_kind,
        vin=result.vin,
        release_date=result.release_date,
        customs_found=result.customs_found,
        message=result.message,
        listing_id=result.listing_id,
        avby_url=result.avby_url,
    )
