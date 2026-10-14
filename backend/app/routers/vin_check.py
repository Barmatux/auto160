"""Authenticated (non-admin) manual VIN CHECK endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.listing_enrichment import perform_listing_vin_check, recheck_listing_customs_import_date
from app.manual_vin_check import (
    ManualVinCheckError,
    run_manual_vin_check_from_url,
    user_has_manual_vin_check_launch,
)
from app.models import CarListing, User, UserRole
from app.schemas import (
    ListingCustomsRecheckResponse,
    ListingVinCheckResponse,
    ManualVinCheckRunItem,
    ManualVinCheckRunRequest,
    ManualVinCheckRunResponse,
)

router = APIRouter(prefix="/api/v1/vin-check", tags=["vin-check"])


def _require_listing_access(db: Session, user: User, listing_id: int) -> CarListing:
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if user.role == UserRole.admin:
        return listing
    if user_has_manual_vin_check_launch(db, user_id=user.id, listing_id=listing_id):
        return listing
    raise HTTPException(status_code=403, detail="Недостаточно прав для проверки этого объявления")


@router.post("/manual/run", response_model=ManualVinCheckRunResponse)
def run_manual_vin_check(
    payload: ManualVinCheckRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = run_manual_vin_check_from_url(
            db,
            payload.url,
            launched_by=current_user,
            run_vin_checks=False,
        )
    except ManualVinCheckError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ManualVinCheckRunResponse(
        kind=result.kind,
        url=result.url,
        advert_count=result.advert_count,
        listing_ids=[item.listing_id for item in result.items],
        items=[
            ManualVinCheckRunItem(
                listing_id=item.listing_id,
                avby_id=item.avby_id,
                created=item.created,
            )
            for item in result.items
        ],
        error=result.error,
    )


@router.post("/listings/{listing_id}/check", response_model=ListingVinCheckResponse)
def check_listing_vin(
    listing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _require_listing_access(db, current_user, listing_id)
    result = perform_listing_vin_check(db, listing, allow_inactive=True)
    return ListingVinCheckResponse(
        listing_id=listing.id,
        vin=result.vin,
        vin_error=result.vin_error,
        release_date=result.release_date,
        customs_found=result.customs_found,
        customs_error=result.customs_error,
    )


@router.post("/listings/{listing_id}/customs-recheck", response_model=ListingCustomsRecheckResponse)
def recheck_listing_customs(
    listing_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _require_listing_access(db, current_user, listing_id)
    release_date, customs_error = recheck_listing_customs_import_date(db, listing)
    return ListingCustomsRecheckResponse(
        listing_id=listing.id,
        release_date=release_date,
        customs_found=release_date is not None,
        customs_error=customs_error,
    )
