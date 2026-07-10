from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.avby_accounts import (
    VIN_TEST_DAILY_LIMIT,
    import_avby_accounts_from_json,
    list_active_vin_accounts,
    normalize_avby_phone,
    serialize_account_public,
    serialize_account_secrets,
)
from app.avby_session import AvbySessionError, get_avby_session
from app.avby_vin import AvbyVinError, get_or_fetch_listing_vin
from app.db import get_db
from app.deps import require_admin
from app.models import AvbyServiceAccount, CarListing, User
from app.schemas import (
    AvbyAccountsImportResult,
    AvbyServiceAccountCreateRequest,
    AvbyServiceAccountPublic,
    AvbyServiceAccountSecrets,
    AvbyServiceAccountUpdateRequest,
    ListingVinResponse,
    UserPublic,
    UserRoleUpdateRequest,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/users", response_model=list[UserPublic])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}/role", response_model=UserPublic)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.id == current_admin.id and payload.role != target_user.role:
        raise HTTPException(status_code=400, detail="Use another admin to change your own role")

    target_user.role = payload.role
    db.commit()
    db.refresh(target_user)
    return target_user


@router.get("/avby-accounts", response_model=list[AvbyServiceAccountPublic])
def list_avby_accounts(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    accounts = db.query(AvbyServiceAccount).order_by(AvbyServiceAccount.created_at.desc()).all()
    return [serialize_account_public(account) for account in accounts]


@router.get("/avby-accounts/{account_id}/secrets", response_model=AvbyServiceAccountSecrets)
def get_avby_account_secrets(
    account_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return serialize_account_secrets(account)


@router.post("/avby-accounts/import-json", response_model=AvbyAccountsImportResult)
def import_avby_accounts_json(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        result = import_avby_accounts_from_json(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.post("/avby-accounts", response_model=AvbyServiceAccountPublic)
def create_avby_account(
    payload: AvbyServiceAccountCreateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    email_raw = (payload.email or "").strip().lower()
    email = email_raw if email_raw and "@" in email_raw else None
    phone = None
    if payload.phone and payload.phone.strip():
        try:
            phone = normalize_avby_phone(payload.phone)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not email and not phone:
        raise HTTPException(status_code=400, detail="Укажите email или номер телефона")
    if not payload.avby_password.strip():
        raise HTTPException(status_code=400, detail="av.by password is required")

    if email:
        existing = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.email == email).first()
        if existing:
            raise HTTPException(status_code=409, detail="Account with this email already exists")
    if phone:
        existing = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.phone == phone).first()
        if existing:
            raise HTTPException(status_code=409, detail="Account with this phone already exists")

    purpose = (payload.purpose or "vin_test").strip() or "vin_test"
    status = "phone_verified" if payload.phone_verified else "confirmed"
    is_active = payload.is_active if payload.is_active is not None else payload.phone_verified
    if purpose == "vin_test" and not payload.phone_verified:
        is_active = False

    account = AvbyServiceAccount(
        email=email,
        phone=phone,
        name=(payload.name or "").strip()[:120],
        avby_password=payload.avby_password,
        api_key=(payload.api_key or "").strip() or None,
        auth_token=(payload.auth_token or "").strip() or None,
        refresh_token=(payload.refresh_token or "").strip() or None,
        status=status,
        purpose=purpose,
        daily_vin_limit=payload.daily_vin_limit or VIN_TEST_DAILY_LIMIT,
        vin_checks_today=0,
        is_active=is_active,
        notes=(payload.notes or "").strip() or None,
        registered_at=datetime.utcnow(),
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    if payload.login_on_create:
        try:
            get_avby_session(db, account)
        except AvbySessionError as exc:
            db.delete(account)
            db.commit()
            raise HTTPException(status_code=502, detail=f"av.by login failed: {exc}") from exc
        db.refresh(account)
        if payload.phone_verified and purpose == "vin_test":
            account.is_active = True
            account.status = "phone_verified"
            db.commit()
            db.refresh(account)

    return serialize_account_public(account)


@router.patch("/avby-accounts/{account_id}", response_model=AvbyServiceAccountPublic)
def update_avby_account(
    account_id: int,
    payload: AvbyServiceAccountUpdateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if payload.is_active is not None:
        account.is_active = payload.is_active
    if payload.notes is not None:
        account.notes = payload.notes.strip() or None
    if payload.daily_vin_limit is not None:
        if payload.daily_vin_limit < 1:
            raise HTTPException(status_code=400, detail="daily_vin_limit must be >= 1")
        account.daily_vin_limit = payload.daily_vin_limit
    db.commit()
    db.refresh(account)
    return serialize_account_public(account)


@router.delete("/avby-accounts/{account_id}")
def delete_avby_account(
    account_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"ok": True}


@router.post("/listings/{listing_id}/vin", response_model=ListingVinResponse)
def fetch_listing_vin(
    listing_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    try:
        result = get_or_fetch_listing_vin(db, listing)
    except AvbyVinError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if not result.vin:
        raise HTTPException(status_code=502, detail="VIN not available")
    return ListingVinResponse(
        listing_id=listing.id,
        vin=result.vin,
        source=result.source or "unknown",
        cached=result.cached,
        checks_remaining=result.checks_remaining,
        fetched_at=result.fetched_at,
    )
