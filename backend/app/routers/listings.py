from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_optional_current_user, require_admin
from app.body_type_labels import exclude_hidden_body_type
from app.listing_embeddings import search_similar
from app.models import CarListing, ListingStatus, User, UserRole
from app.schemas import ListingCreate, ListingOut, ListingUpdate

router = APIRouter(prefix="/api/v1/listings", tags=["listings"])


class SemanticListingOut(BaseModel):
    id: int
    title: str
    brand: str
    model: str
    year: int
    price: Decimal | None = None
    city: str
    source: str | None = None
    source_url: str | None = None
    cover_photo_url: str | None = None
    status: ListingStatus
    distance: float = Field(description="Cosine distance (lower is closer)")

    class Config:
        from_attributes = True


@router.get("", response_model=list[ListingOut])
def list_listings(
    brand: str | None = Query(default=None),
    city: str | None = Query(default=None),
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    query = exclude_hidden_body_type(db.query(CarListing), CarListing.body_type)

    if current_user is None or current_user.role != UserRole.admin:
        query = query.filter(CarListing.status == ListingStatus.published)

    if brand:
        query = query.filter(CarListing.brand.ilike(f"%{brand}%"))
    if city:
        query = query.filter(CarListing.city.ilike(f"%{city}%"))
    if min_price is not None:
        query = query.filter(CarListing.price >= min_price)
    if max_price is not None:
        query = query.filter(CarListing.price <= max_price)

    return query.order_by(desc(CarListing.created_at)).offset(offset).limit(limit).all()


@router.get("/meta/statuses", response_model=list[str])
def listing_statuses():
    return [status.value for status in ListingStatus]


@router.get("/semantic", response_model=list[SemanticListingOut])
def semantic_search_listings(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    try:
        rows = search_similar(db, q, limit=limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface provider errors cleanly
        raise HTTPException(status_code=502, detail=f"embedding failed: {exc}") from exc

    return [
        SemanticListingOut(
            id=listing.id,
            title=listing.title,
            brand=listing.brand,
            model=listing.model,
            year=listing.year,
            price=listing.price,
            city=listing.city,
            source=listing.source,
            source_url=listing.source_url,
            cover_photo_url=listing.cover_photo_url,
            status=listing.status,
            distance=distance,
        )
        for listing, distance in rows
    ]


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(
    listing_id: int,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status == ListingStatus.published:
        return listing

    if current_user is None or current_user.role != UserRole.admin:
        raise HTTPException(status_code=404, detail="Listing not found")

    return listing


@router.post("", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(
    payload: ListingCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    listing = CarListing(seller_id=current_user.id, **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    payload: ListingUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(listing, field, value)

    db.commit()
    db.refresh(listing)
    return listing


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(
    listing_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    db.delete(listing)
    db.commit()
    return None
