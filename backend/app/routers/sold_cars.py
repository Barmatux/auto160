"""Admin-only API for the sold-cars archive (imported from Excel)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import require_admin_flexible
from app.models import SoldCar, SoldCarExpense, SoldPartner, User

router = APIRouter(prefix="/api/v1/admin/sold-cars", tags=["sold-cars"])

CURRENCIES = {"BYN", "USD", "EUR"}


class ExpenseIn(BaseModel):
    item: str = Field(min_length=1, max_length=300)
    amount: float
    currency: str = "BYN"
    payer: str | None = Field(default=None, max_length=40)
    note: str | None = None


class ExpenseOut(BaseModel):
    id: int
    row_no: int
    item: str
    amount: float
    currency: str
    payer: str | None = None
    note: str | None = None


class SoldCarSummary(BaseModel):
    id: int
    title: str
    sheet: str | None = None
    sold_date: date | None = None
    sold_price: float | None = None
    cost_price: float | None = None
    commission: float | None = None
    profit: float | None = None
    needs_review: bool
    verified: bool
    locked: bool
    expenses_count: int
    sums: dict[str, Any] = Field(default_factory=dict)
    payers: list[str] = Field(default_factory=list)
    updated_at: datetime


class SoldCarDetail(SoldCarSummary):
    fx_rate: float | None = None
    notes: str | None = None
    flags: list[str] = Field(default_factory=list)
    figures: list[dict[str, Any]] = Field(default_factory=list)
    sheet_totals: dict[str, Any] | None = None
    raw_grid: list[dict[str, Any]] = Field(default_factory=list)
    expenses: list[ExpenseOut] = Field(default_factory=list)


class SoldCarPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    sold_date: date | None = None
    sold_price: float | None = None
    cost_price: float | None = None
    commission: float | None = None
    profit: float | None = None
    fx_rate: float | None = None
    notes: str | None = None
    needs_review: bool | None = None
    expenses: list[ExpenseIn] | None = None
    clear_fields: list[str] = Field(default_factory=list)


class ImportExpense(BaseModel):
    row: int = 0
    item: str
    amount: float
    currency: str
    payer: str | None = None
    note: str | None = None


class ImportCar(BaseModel):
    source_key: str
    sheet: str | None = None
    title: str
    expenses: list[ImportExpense] = Field(default_factory=list)
    sums: dict[str, Any] = Field(default_factory=dict)
    sheet_totals: dict[str, Any] | None = None
    figures: list[dict[str, Any]] = Field(default_factory=list)
    sold_price: float | None = None
    cost_price: float | None = None
    profit: float | None = None
    commission: float | None = None
    fx_rate: float | None = None
    verified: bool = False
    needs_review: bool = True
    flags: list[str] = Field(default_factory=list)
    raw_grid: list[dict[str, Any]] = Field(default_factory=list)


class ImportRequest(BaseModel):
    cars: list[ImportCar] = Field(default_factory=list)
    cash_sheets: list[dict[str, Any]] = Field(default_factory=list)


class ImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped_locked: int = 0
    partners_added: int = 0
    total: int = 0


class PartnerOut(BaseModel):
    id: int
    code: str
    name: str | None = None
    expenses_count: int = 0


class PartnerPatch(BaseModel):
    name: str | None = Field(default=None, max_length=160)


def _num(v: Any) -> float | None:
    return None if v is None else float(v)


def _summary(car: SoldCar) -> dict[str, Any]:
    payers = sorted({e.payer_code for e in car.expenses if e.payer_code})
    return {
        "id": car.id,
        "title": car.title,
        "sheet": car.sheet,
        "sold_date": car.sold_date,
        "sold_price": _num(car.sold_price),
        "cost_price": _num(car.cost_price),
        "commission": _num(car.commission),
        "profit": _num(car.profit),
        "needs_review": car.needs_review,
        "verified": car.verified,
        "locked": car.locked,
        "expenses_count": len(car.expenses),
        "sums": car.sums or {},
        "payers": payers,
        "updated_at": car.updated_at,
    }


def _detail(car: SoldCar) -> dict[str, Any]:
    data = _summary(car)
    data.update(
        {
            "fx_rate": _num(car.fx_rate),
            "notes": car.notes,
            "flags": list(car.flags or []),
            "figures": list(car.figures or []),
            "sheet_totals": car.sheet_totals,
            "raw_grid": list(car.raw_grid or []),
            "expenses": [
                {
                    "id": e.id,
                    "row_no": e.row_no,
                    "item": e.item,
                    "amount": float(e.amount),
                    "currency": e.currency,
                    "payer": e.payer_code,
                    "note": e.note,
                }
                for e in car.expenses
            ],
        }
    )
    return data


def _ensure_partners(db: Session, codes: set[str]) -> int:
    codes = {c for c in codes if c}
    if not codes:
        return 0
    existing = {c for (c,) in db.query(SoldPartner.code).filter(SoldPartner.code.in_(codes)).all()}
    added = 0
    for code in sorted(codes - existing):
        db.add(SoldPartner(code=code))
        added += 1
    return added


def _get_car(db: Session, car_id: int) -> SoldCar:
    car = (
        db.query(SoldCar)
        .options(selectinload(SoldCar.expenses))
        .filter(SoldCar.id == car_id)
        .first()
    )
    if car is None:
        raise HTTPException(status_code=404, detail="Авто не найдено")
    return car


@router.get("", response_model=list[SoldCarSummary])
def list_sold_cars(_: User = Depends(require_admin_flexible), db: Session = Depends(get_db)):
    cars = (
        db.query(SoldCar)
        .options(selectinload(SoldCar.expenses))
        .order_by(SoldCar.needs_review.desc(), SoldCar.sheet, SoldCar.id)
        .all()
    )
    return [_summary(c) for c in cars]


@router.get("/partners", response_model=list[PartnerOut])
def list_partners(_: User = Depends(require_admin_flexible), db: Session = Depends(get_db)):
    counts: dict[str, int] = {}
    for code, in db.query(SoldCarExpense.payer_code).filter(SoldCarExpense.payer_code.isnot(None)).all():
        counts[code] = counts.get(code, 0) + 1
    partners = db.query(SoldPartner).order_by(SoldPartner.code).all()
    return [
        {"id": p.id, "code": p.code, "name": p.name, "expenses_count": counts.get(p.code, 0)}
        for p in partners
    ]


@router.patch("/partners/{partner_id}", response_model=PartnerOut)
def patch_partner(
    partner_id: int,
    payload: PartnerPatch,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    partner = db.query(SoldPartner).filter(SoldPartner.id == partner_id).first()
    if partner is None:
        raise HTTPException(status_code=404, detail="Партнёр не найден")
    partner.name = (payload.name or "").strip() or None
    db.commit()
    db.refresh(partner)
    count = db.query(SoldCarExpense).filter(SoldCarExpense.payer_code == partner.code).count()
    return {"id": partner.id, "code": partner.code, "name": partner.name, "expenses_count": count}


@router.post("/import", response_model=ImportResult)
def import_sold_cars(
    payload: ImportRequest,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    """Idempotent upsert by source_key. Hand-edited (locked) cars are never overwritten."""
    result = ImportResult(total=len(payload.cars))
    payer_codes: set[str] = set()
    now = datetime.utcnow()
    for item in payload.cars:
        car = db.query(SoldCar).filter(SoldCar.source_key == item.source_key).first()
        if car is not None and car.locked:
            result.skipped_locked += 1
            continue
        created = car is None
        if created:
            car = SoldCar(source_key=item.source_key, created_at=now)
            db.add(car)
        car.sheet = item.sheet
        car.title = item.title.strip()[:300]
        car.sold_price = item.sold_price
        car.cost_price = item.cost_price
        car.profit = item.profit
        car.commission = item.commission
        car.fx_rate = item.fx_rate
        car.needs_review = item.needs_review
        car.verified = item.verified
        car.flags = item.flags
        car.figures = item.figures
        car.sums = item.sums
        car.sheet_totals = item.sheet_totals
        car.raw_grid = item.raw_grid
        car.updated_at = now
        car.expenses.clear()
        for exp in item.expenses:
            cur = exp.currency.upper()
            if cur not in CURRENCIES:
                continue
            if exp.payer:
                payer_codes.add(exp.payer)
            car.expenses.append(
                SoldCarExpense(
                    row_no=exp.row,
                    item=exp.item.strip()[:300] or "(без названия)",
                    amount=exp.amount,
                    currency=cur,
                    payer_code=exp.payer,
                    note=exp.note,
                )
            )
        if created:
            result.created += 1
        else:
            result.updated += 1
    result.partners_added = _ensure_partners(db, payer_codes)
    db.commit()
    return result


@router.get("/{car_id}", response_model=SoldCarDetail)
def get_sold_car(car_id: int, _: User = Depends(require_admin_flexible), db: Session = Depends(get_db)):
    return _detail(_get_car(db, car_id))


@router.patch("/{car_id}", response_model=SoldCarDetail)
def patch_sold_car(
    car_id: int,
    payload: SoldCarPatch,
    _: User = Depends(require_admin_flexible),
    db: Session = Depends(get_db),
):
    car = _get_car(db, car_id)
    data = payload.model_dump(exclude_unset=True)
    clear = set(data.pop("clear_fields", []) or [])
    expenses = data.pop("expenses", None)
    allowed = {"title", "sold_date", "sold_price", "cost_price", "commission", "profit", "fx_rate", "notes", "needs_review"}
    for key, value in data.items():
        if key in allowed and value is not None:
            setattr(car, key, value.strip() if isinstance(value, str) else value)
    for key in clear & {"sold_date", "sold_price", "cost_price", "commission", "profit", "fx_rate", "notes"}:
        setattr(car, key, None)
    if expenses is not None:
        car.expenses.clear()
        codes: set[str] = set()
        for idx, exp in enumerate(payload.expenses or [], start=1):
            cur = exp.currency.upper()
            if cur not in CURRENCIES:
                raise HTTPException(status_code=422, detail=f"Валюта {exp.currency}: допустимы BYN, USD, EUR")
            code = (exp.payer or "").strip() or None
            if code:
                codes.add(code)
            car.expenses.append(
                SoldCarExpense(
                    row_no=idx,
                    item=exp.item.strip()[:300],
                    amount=exp.amount,
                    currency=cur,
                    payer_code=code,
                    note=(exp.note or "").strip() or None,
                )
            )
        _ensure_partners(db, codes)
    car.locked = True
    car.updated_at = datetime.utcnow()
    db.commit()
    return _detail(_get_car(db, car_id))


@router.delete("/{car_id}", status_code=204)
def delete_sold_car(car_id: int, _: User = Depends(require_admin_flexible), db: Session = Depends(get_db)):
    car = _get_car(db, car_id)
    db.delete(car)
    db.commit()
    return None
