from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.analytics import build_analytics_summary
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
from app.listing_enrichment import (
    apply_manual_listing_vin,
    perform_listing_vin_check,
    recheck_listing_customs_import_date,
)
from app.manual_vin_check import (
    ManualVinCheckError,
    run_manual_vin_check_from_url,
    user_has_manual_vin_check_launch,
)
from app.catalog_generation_years import apply_generation_years, sync_generation_years_from_sources
from app.arbitrage_analytics import invalidate_arbitrage_cache
from app.catalog_ratings import (
    apply_generation_arbitrage_track,
    apply_generation_rating,
    format_production_years,
    generation_label,
)
from app.catalog_visibility import apply_generation_catalog_visibility
from app.db import get_db
from app.deps import require_admin, require_admin_flexible
from app.customs_vehicles import (
    create_customs_vehicle_spec,
    delete_customs_vehicle_spec,
    list_customs_vehicle_specs,
    update_customs_vehicle_spec,
)
from app.featured import (
    add_featured_listing,
    list_featured_rows,
    list_site_leads,
    mark_site_lead_read,
    remove_featured_listing,
    set_featured_active,
)
from app.logging_setup import LOG_SERVICES, format_log_time, log_dir, log_timezone, tail_log
from app.models import AvbyServiceAccount, CarListing, User, UserRole
from app.schemas import (
    AnalyticsSummaryResponse,
    AvbyAccountsImportResult,
    AvbyServiceAccountCreateRequest,
    AvbyServiceAccountPublic,
    AvbyServiceAccountSecrets,
    AvbyServiceAccountUpdateRequest,
    AppLogTailResponse,
    CatalogGenerationArbitrageTrackResult,
    CatalogGenerationArbitrageTrackUpdate,
    CatalogGenerationRatingResult,
    CatalogGenerationRatingUpdate,
    CatalogGenerationVisibilityResult,
    CatalogGenerationVisibilityUpdate,
    CatalogGenerationYearsResult,
    CatalogGenerationYearsUpdate,
    CustomsVehicleSpecCreateRequest,
    CustomsVehicleSpecOut,
    CustomsVehicleSpecUpdateRequest,
    FeaturedListingActiveRequest,
    FeaturedListingCreateRequest,
    FeaturedListingOut,
    ListingCustomsRecheckResponse,
    ListingManualVinRequest,
    ListingVinCheckResponse,
    ListingVinResponse,
    ManualVinCheckRunRequest,
    ManualVinCheckRunItem,
    ManualVinCheckRunResponse,
    SiteLeadOut,
    SiteLeadReadRequest,
    UserPublic,
    UserRoleUpdateRequest,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/logs", response_model=AppLogTailResponse)
def tail_application_logs(
    service: str = Query(default="api"),
    lines: int = Query(default=200, ge=10, le=2000),
    _: User = Depends(require_admin_flexible),
):
    if service not in LOG_SERVICES:
        raise HTTPException(status_code=400, detail=f"Unknown service. Allowed: {', '.join(LOG_SERVICES)}")
    try:
        content, path = tail_log(service, lines=lines)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AppLogTailResponse(
        service=service,
        lines=lines,
        content=content,
        path=str(path) if path else None,
        log_dir=str(log_dir()),
        fetched_at=format_log_time(),
    )


@router.get("/analytics", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(
    days: int = Query(default=7, ge=1, le=90),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return build_analytics_summary(db, days=days)


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
        avby_password=payload.avby_password.strip(),
        api_key=(payload.api_key or "").strip() or None,
        auth_token=(payload.auth_token or "").strip() or None,
        refresh_token=(payload.refresh_token or "").strip() or None,
        status=status,
        purpose=purpose,
        daily_vin_limit=payload.daily_vin_limit if payload.daily_vin_limit is not None else None,
        vin_checks_today=0,
        is_active=is_active,
        notes=(payload.notes or "").strip() or None,
        registered_at=datetime.utcnow(),
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    login_error: str | None = None
    if payload.login_on_create:
        try:
            get_avby_session(db, account, allow_captcha=True)
            account.error_message = None
            if payload.phone_verified and purpose == "vin_test":
                account.is_active = True
                account.status = "phone_verified"
            db.commit()
            db.refresh(account)
        except AvbySessionError as exc:
            login_error = str(exc)
            account.is_active = False
            account.error_message = login_error[:500]
            if account.status not in {"phone_verified", "confirmed"}:
                account.status = "failed"
            db.commit()
            db.refresh(account)

    result = serialize_account_public(account)
    if login_error:
        result["login_error"] = login_error
    return result


@router.post("/avby-accounts/{account_id}/login", response_model=AvbyServiceAccountPublic)
def login_avby_account(
    account_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not account.avby_password:
        raise HTTPException(status_code=400, detail="Account has no av.by password")

    try:
        get_avby_session(db, account, allow_captcha=True)
    except AvbySessionError as exc:
        account.is_active = False
        account.error_message = str(exc)[:500]
        db.commit()
        db.refresh(account)
        result = serialize_account_public(account)
        result["login_error"] = str(exc)
        return result

    account.error_message = None
    if account.status in {"failed", "pending", "mailtm_only"}:
        account.status = "phone_verified" if account.phone else "confirmed"
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
        # 0 clears the local cut-off (usage is still counted).
        if payload.daily_vin_limit < 0:
            raise HTTPException(status_code=400, detail="daily_vin_limit must be >= 0")
        account.daily_vin_limit = payload.daily_vin_limit or None
    if payload.email is not None:
        email_raw = payload.email.strip().lower()
        email = email_raw if email_raw and "@" in email_raw else None
        if email:
            existing = (
                db.query(AvbyServiceAccount)
                .filter(AvbyServiceAccount.email == email, AvbyServiceAccount.id != account_id)
                .first()
            )
            if existing:
                raise HTTPException(status_code=409, detail="Account with this email already exists")
        account.email = email
    if payload.avby_password is not None:
        password = payload.avby_password.strip()
        if not password:
            raise HTTPException(status_code=400, detail="av.by password cannot be empty")
        account.avby_password = password
        account.error_message = None
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


@router.patch("/catalog-ratings", response_model=CatalogGenerationRatingResult)
def update_catalog_generation_rating(
    payload: CatalogGenerationRatingUpdate,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    items, updated = apply_generation_rating(
        db,
        make=payload.make,
        model=payload.model,
        generation=payload.generation,
        rating=payload.rating,
    )
    if not items:
        raise HTTPException(status_code=404, detail="Поколение не найдено в каталоге")
    db.commit()
    return CatalogGenerationRatingResult(
        make=payload.make.strip(),
        model=payload.model.strip(),
        generation=generation_label(payload.generation),
        rating=payload.rating,
        updated_items=updated,
    )


@router.patch("/catalog-generations/visibility", response_model=CatalogGenerationVisibilityResult)
def update_catalog_generation_visibility(
    payload: CatalogGenerationVisibilityUpdate,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    result = apply_generation_catalog_visibility(
        db,
        make=payload.make,
        model=payload.model,
        generation=payload.generation,
        hidden=payload.hidden,
    )
    if not result.items:
        raise HTTPException(status_code=404, detail="Поколение не найдено в каталоге")
    db.commit()
    return CatalogGenerationVisibilityResult(
        make=payload.make.strip(),
        model=payload.model.strip(),
        generation=generation_label(payload.generation),
        hidden=payload.hidden,
        updated_items=result.updated_items,
        archived_listings=result.archived_listings,
    )


@router.patch(
    "/catalog-generations/arbitrage-track",
    response_model=CatalogGenerationArbitrageTrackResult,
)
def update_catalog_generation_arbitrage_track(
    payload: CatalogGenerationArbitrageTrackUpdate,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    items, updated = apply_generation_arbitrage_track(
        db,
        make=payload.make,
        model=payload.model,
        generation=payload.generation,
        enabled=payload.enabled,
    )
    if not items:
        raise HTTPException(status_code=404, detail="Поколение не найдено в каталоге")
    db.commit()
    invalidate_arbitrage_cache()
    return CatalogGenerationArbitrageTrackResult(
        make=payload.make.strip(),
        model=payload.model.strip(),
        generation=generation_label(payload.generation),
        enabled=bool(payload.enabled),
        updated_items=updated,
    )


@router.patch("/catalog-generations/years", response_model=CatalogGenerationYearsResult)
def update_catalog_generation_years(
    payload: CatalogGenerationYearsUpdate,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    try:
        items, updated = apply_generation_years(
            db,
            make=payload.make,
            model=payload.model,
            generation=payload.generation,
            year_from=payload.year_from,
            year_to=payload.year_to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not items:
        raise HTTPException(status_code=404, detail="Поколение не найдено в каталоге")
    db.commit()
    return CatalogGenerationYearsResult(
        make=payload.make.strip(),
        model=payload.model.strip(),
        generation=generation_label(payload.generation),
        year_from=payload.year_from,
        year_to=payload.year_to,
        production_years=format_production_years(payload.year_from, payload.year_to),
        updated_items=updated,
    )


@router.post("/catalog-generations/years/sync", response_model=CatalogGenerationYearsResult)
def sync_catalog_generation_years_from_avby(
    payload: CatalogGenerationYearsUpdate,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    items, updated, production_years = sync_generation_years_from_sources(
        db,
        make=payload.make,
        model=payload.model,
        generation=payload.generation,
    )
    if not items:
        raise HTTPException(status_code=404, detail="Поколение не найдено в каталоге")
    if updated == 0:
        raise HTTPException(
            status_code=404,
            detail="Не удалось определить годы из сохранённых данных av.by. Задайте вручную или переимпортируйте поколение.",
        )
    db.commit()
    sample = items[0]
    return CatalogGenerationYearsResult(
        make=payload.make.strip(),
        model=payload.model.strip(),
        generation=generation_label(payload.generation),
        year_from=sample.year_from,
        year_to=sample.year_to,
        production_years=production_years,
        updated_items=updated,
    )


def _require_manual_vin_listing_access(db: Session, user: User, listing_id: int) -> CarListing:
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if user.role == UserRole.admin:
        return listing
    if user_has_manual_vin_check_launch(db, user_id=user.id, listing_id=listing_id):
        return listing
    raise HTTPException(status_code=403, detail="Недостаточно прав для проверки этого объявления")


@router.post("/listings/{listing_id}/customs-recheck", response_model=ListingCustomsRecheckResponse)
def recheck_listing_customs(
    listing_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    listing = _require_manual_vin_listing_access(db, current_user, listing_id)
    release_date, customs_error = recheck_listing_customs_import_date(db, listing)
    return ListingCustomsRecheckResponse(
        listing_id=listing.id,
        release_date=release_date,
        customs_found=release_date is not None,
        customs_error=customs_error,
    )


@router.post("/listings/{listing_id}/vin-check", response_model=ListingVinCheckResponse)
def fetch_listing_vin_check(
    listing_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    listing = _require_manual_vin_listing_access(db, current_user, listing_id)
    result = perform_listing_vin_check(db, listing, allow_inactive=True)
    return ListingVinCheckResponse(
        listing_id=listing.id,
        vin=result.vin,
        vin_error=result.vin_error,
        release_date=result.release_date,
        customs_found=result.customs_found,
        customs_error=result.customs_error,
    )


@router.post("/vin-check/manual/run", response_model=ManualVinCheckRunResponse)
def run_manual_vin_check(
    payload: ManualVinCheckRunRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Ingest av.by listing/search URL into DB; client then runs per-listing VIN CHECK."""
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


@router.post("/listings/{listing_id}/vin-manual", response_model=ListingVinCheckResponse)
def save_manual_listing_vin(
    listing_id: int,
    payload: ListingManualVinRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    listing = db.query(CarListing).filter(CarListing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    result = apply_manual_listing_vin(db, listing, payload.vin)
    if result.vin_error and not result.vin:
        raise HTTPException(status_code=400, detail=result.vin_error)
    return ListingVinCheckResponse(
        listing_id=listing.id,
        vin=result.vin,
        vin_error=result.vin_error,
        release_date=result.release_date,
        customs_found=result.customs_found,
        customs_error=result.customs_error,
    )


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
        result = get_or_fetch_listing_vin(db, listing, allow_inactive=True)
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


@router.get("/featured-listings", response_model=list[FeaturedListingOut])
def admin_list_featured_listings(
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    return list_featured_rows(db)


@router.post("/featured-listings", response_model=FeaturedListingOut)
def admin_add_featured_listing(
    payload: FeaturedListingCreateRequest,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    try:
        return add_featured_listing(db, payload.listing_id, sort_weight=payload.sort_weight)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/featured-listings/{featured_id}/active", response_model=FeaturedListingOut)
def admin_set_featured_active(
    featured_id: int,
    payload: FeaturedListingActiveRequest,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    try:
        return set_featured_active(db, featured_id, is_active=payload.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/featured-listings/{featured_id}", status_code=204)
def admin_remove_featured_listing(
    featured_id: int,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    try:
        remove_featured_listing(db, featured_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None


@router.get("/customs-vehicles", response_model=list[CustomsVehicleSpecOut])
def admin_list_customs_vehicles(
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    return list_customs_vehicle_specs(db, active_only=False)


@router.post("/customs-vehicles", response_model=CustomsVehicleSpecOut)
def admin_create_customs_vehicle(
    payload: CustomsVehicleSpecCreateRequest,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    try:
        return create_customs_vehicle_spec(
            db,
            make=payload.make,
            model=payload.model,
            generation=payload.generation,
            year_from=payload.year_from,
            year_to=payload.year_to,
            engine_cc=payload.engine_cc,
            power_hp=payload.power_hp,
            engine_kind=payload.engine_kind,
            fuel_label=payload.fuel_label,
            notes=payload.notes,
            is_active=payload.is_active,
            sort_weight=payload.sort_weight,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/customs-vehicles/{spec_id}", response_model=CustomsVehicleSpecOut)
def admin_update_customs_vehicle(
    spec_id: int,
    payload: CustomsVehicleSpecUpdateRequest,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    try:
        data = payload.model_dump(exclude_unset=True)
        return update_customs_vehicle_spec(db, spec_id, **data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/customs-vehicles/{spec_id}", status_code=204)
def admin_delete_customs_vehicle(
    spec_id: int,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    try:
        delete_customs_vehicle_spec(db, spec_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None


@router.get("/site-leads", response_model=list[SiteLeadOut])
def admin_list_site_leads(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    return list_site_leads(db, limit=limit, offset=offset)


@router.post("/site-leads/{lead_id}/read", response_model=SiteLeadOut)
def admin_mark_site_lead_read(
    lead_id: int,
    payload: SiteLeadReadRequest,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    try:
        return mark_site_lead_read(db, lead_id, is_read=payload.is_read)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
