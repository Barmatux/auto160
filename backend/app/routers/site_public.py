"""Public endpoints for Belarus landing leads, import-date lookup, and customs calc."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.customs_catalog import (
    engine_cc_from_item,
    engine_kind_from_item,
    get_item as get_catalog_item,
    list_makes as list_catalog_makes_for_customs,
    list_models as list_catalog_models_for_customs,
    list_motors as list_catalog_motors_for_customs,
    motor_label as catalog_motor_label,
    power_hp_from_item,
)
from app.customs_db import (
    cc_label,
    get_cc,
    list_ccs,
    list_liters,
    list_motors_for_model,
    motor_label as customs_db_motor_label,
    public_make_names,
    public_models_for_make_name,
)
from app.customs_duty_calc import CustomsCalcInput, calculate_customs, normalize_age_band
from app.customs_vehicles import (
    get_customs_vehicle_spec,
    list_customs_vehicle_specs,
    list_makes as list_legacy_makes,
    list_models_for_make as list_legacy_models_for_make,
)
from app.db import get_db
from app.deps import get_optional_user_flexible
from app.featured import create_site_lead, lookup_public_import_date, run_public_inspection_check
from app.models import User, UserRole
from app.myfin_rates import fetch_myfin_buy_rates
from app.schemas import (
    CustomsCalcRequest,
    CustomsCalcResponse,
    CustomsCatalogModelOut,
    CustomsCatalogMotorOut,
    CustomsDbCcOut,
    CustomsDbLiterOut,
    CustomsDbModelOut,
    CustomsDbMotorOut,
    CustomsVehicleSpecOut,
    ImportDateLookupRequest,
    ImportDateLookupResponse,
    InspectionCheckRequest,
    InspectionCheckResponse,
    SiteLeadCreateRequest,
    SiteLeadOut,
)

router = APIRouter(prefix="/api/v1/public", tags=["public"])

_FALLBACK_EUR_RUB = 98.0
_FALLBACK_USD_RUB = 90.0
_FALLBACK_BYN_RUB = 28.0


def _fx_triplet() -> tuple[float, float, float]:
    rates = fetch_myfin_buy_rates()
    if rates is None:
        return _FALLBACK_EUR_RUB, _FALLBACK_USD_RUB, _FALLBACK_BYN_RUB
    return rates.eur_rub, rates.usd_rub, rates.byn_rub


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


@router.post("/inspection-check", response_model=InspectionCheckResponse)
def public_inspection_check(
    payload: InspectionCheckRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user_flexible),
):
    reveal_vin = bool(current_user and current_user.role == UserRole.admin)
    result = run_public_inspection_check(db, payload.query, reveal_vin=reveal_vin)
    return InspectionCheckResponse(
        ok=result.ok,
        input_kind=result.input_kind,
        vin=result.vin,
        release_date=result.release_date,
        customs_found=result.customs_found,
        customs_status=result.customs_status,
        message=result.message,
        listing_id=result.listing_id,
        avby_url=result.avby_url,
        query=result.query,
        power_hp=result.power_hp,
        engine_capacity_l=result.engine_capacity_l,
        engine_cc=result.engine_cc,
        engine_cc_approximate=result.engine_cc_approximate,
        brand=result.brand,
        model=result.model,
        year=result.year,
        verdict=result.verdict,
    )


@router.get("/customs-db/makes", response_model=list[str])
def public_customs_db_makes(db: Session = Depends(get_db)):
    names = public_make_names(db)
    if names:
        return names
    return list_legacy_makes(db)


@router.get("/customs-db/models", response_model=list[CustomsDbModelOut])
def public_customs_db_models(make: str = Query(...), db: Session = Depends(get_db)):
    return public_models_for_make_name(db, make)


@router.get("/customs-db/liters", response_model=list[CustomsDbLiterOut])
def public_customs_db_liters(model_id: int = Query(...), db: Session = Depends(get_db)):
    return list_liters(db, model_id, active_only=True)


@router.get("/customs-db/ccs", response_model=list[CustomsDbCcOut])
def public_customs_db_ccs(liter_id: int = Query(...), db: Session = Depends(get_db)):
    return list_ccs(db, liter_id, active_only=True)


@router.get("/customs-db/motors", response_model=list[CustomsDbMotorOut])
def public_customs_db_motors(model_id: int = Query(...), db: Session = Depends(get_db)):
    rows = list_motors_for_model(db, model_id, active_only=True)
    return [
        CustomsDbMotorOut(
            id=row.id,
            liter_id=row.liter_id,
            liters=float(row.liter.liters) if row.liter is not None else 0.0,
            engine_cc=int(row.engine_cc),
            power_hp=float(row.power_hp) if row.power_hp is not None else None,
            notes=row.notes,
            label=customs_db_motor_label(row),
        )
        for row in rows
    ]


@router.get("/customs-catalog/makes", response_model=list[str])
def public_customs_catalog_makes(db: Session = Depends(get_db)):
    return list_catalog_makes_for_customs(db)


@router.get("/customs-catalog/models", response_model=list[CustomsCatalogModelOut])
def public_customs_catalog_models(make: str = Query(...), db: Session = Depends(get_db)):
    return [CustomsCatalogModelOut(**row) for row in list_catalog_models_for_customs(db, make)]


@router.get("/customs-catalog/motors", response_model=list[CustomsCatalogMotorOut])
def public_customs_catalog_motors(
    make: str = Query(...),
    model: str = Query(...),
    db: Session = Depends(get_db),
):
    return [CustomsCatalogMotorOut(**row) for row in list_catalog_motors_for_customs(db, make, model)]


@router.get("/customs-vehicles/makes", response_model=list[str])
def public_customs_makes(db: Session = Depends(get_db)):
    names = list_catalog_makes_for_customs(db)
    if names:
        return names
    names = public_make_names(db)
    if names:
        return names
    return list_legacy_makes(db)


@router.get("/customs-vehicles", response_model=list[CustomsVehicleSpecOut])
def public_customs_vehicles(
    make: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if make:
        return list_legacy_models_for_make(db, make)
    return list_customs_vehicle_specs(db, active_only=True)


@router.post("/customs-calc", response_model=CustomsCalcResponse)
def public_customs_calc(payload: CustomsCalcRequest, db: Session = Depends(get_db)):
    vehicle_label = None
    engine_cc = payload.engine_cc
    power_hp = payload.power_hp
    engine_kind = payload.engine_kind if payload.engine_kind in {"ice", "electric"} else "ice"

    try:
        age_band = normalize_age_band(payload.age_band)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if payload.catalog_item_id:
        item = get_catalog_item(db, payload.catalog_item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Конфигурация каталога не найдена")
        resolved_cc = engine_cc_from_item(item)
        resolved_hp = power_hp_from_item(item)
        if resolved_hp is None:
            raise HTTPException(status_code=400, detail="У конфигурации нет мощности в каталоге")
        engine_kind = engine_kind_from_item(item)
        if engine_kind != "electric" and not resolved_cc:
            raise HTTPException(status_code=400, detail="У конфигурации нет объёма двигателя в каталоге")
        engine_cc = float(resolved_cc or 0)
        power_hp = float(resolved_hp)
        vehicle_label = " · ".join(
            part
            for part in [
                item.make,
                item.model,
                catalog_motor_label(item, engine_cc=resolved_cc, power_hp=resolved_hp),
            ]
            if part
        )
    elif payload.engine_cc_id:
        row = get_cc(db, payload.engine_cc_id)
        if row is None or not row.is_active:
            raise HTTPException(status_code=404, detail="Объём двигателя не найден")
        engine_cc = float(row.engine_cc)
        if row.power_hp is not None:
            power_hp = float(row.power_hp)
        vehicle_label = cc_label(row)
        engine_kind = "ice"
    elif payload.vehicle_spec_id:
        spec = get_customs_vehicle_spec(db, payload.vehicle_spec_id)
        if spec is None or not spec.is_active:
            raise HTTPException(status_code=404, detail="Комплектация не найдена")
        engine_cc = float(spec.engine_cc)
        power_hp = float(spec.power_hp)
        engine_kind = spec.engine_kind if spec.engine_kind in {"ice", "electric"} else "ice"
        parts = [spec.make, spec.model]
        if spec.generation:
            parts.append(spec.generation)
        parts.append(f"{int(spec.engine_cc)} см³")
        parts.append(f"{spec.power_hp:g} л.с.")
        vehicle_label = " · ".join(parts)

    if payload.importer not in {"personal", "commercial"}:
        raise HTTPException(status_code=400, detail="importer: personal или commercial")
    if payload.currency not in {"RUB", "EUR", "USD", "BYN"}:
        raise HTTPException(status_code=400, detail="Неизвестная валюта")

    eur_rub, usd_rub, byn_rub = _fx_triplet()
    result = calculate_customs(
        CustomsCalcInput(
            age_band=age_band,
            engine_cc=float(engine_cc or 0),
            power_hp=float(power_hp),
            price=float(payload.price),
            currency=payload.currency,  # type: ignore[arg-type]
            importer=payload.importer,  # type: ignore[arg-type]
            engine_kind=engine_kind,  # type: ignore[arg-type]
        ),
        eur_rub=eur_rub,
        usd_rub=usd_rub,
        byn_rub=byn_rub,
    )
    data = result.to_dict()
    data["vehicle_label"] = vehicle_label
    return CustomsCalcResponse(**data)
