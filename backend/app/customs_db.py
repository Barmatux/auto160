"""Hierarchical customs calculator catalog: make → model → liters → exact cc."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import asc, desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models import CustomsDbEngineCc, CustomsDbEngineLiter, CustomsDbMake, CustomsDbModel


def _now() -> datetime:
    return datetime.utcnow()


def _clean_name(value: str | None, label: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"Укажите {label}")
    return cleaned


def _parse_liters(value: float | str | Decimal) -> Decimal:
    try:
        liters = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Объём в литрах: число с одним знаком после запятой") from exc
    if liters <= 0 or liters > 20:
        raise ValueError("Объём в литрах должен быть от 0.1 до 20.0")
    return liters


def _parse_cc(value: int | float | str) -> int:
    try:
        cc = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Объём в см³ должен быть целым числом") from exc
    if cc <= 0 or cc > 20000:
        raise ValueError("Объём в см³ должен быть от 1 до 20000")
    return cc


# —— Makes ——


def list_makes(db: Session, *, active_only: bool = False) -> list[CustomsDbMake]:
    q = db.query(CustomsDbMake)
    if active_only:
        q = q.filter(CustomsDbMake.is_active.is_(True))
    return q.order_by(desc(CustomsDbMake.sort_weight), asc(CustomsDbMake.name), asc(CustomsDbMake.id)).all()


def create_make(db: Session, *, name: str, sort_weight: int = 0) -> CustomsDbMake:
    name_clean = _clean_name(name, "марку")
    existing = (
        db.query(CustomsDbMake)
        .filter(func.lower(CustomsDbMake.name) == name_clean.lower())
        .first()
    )
    if existing is not None:
        return existing
    row = CustomsDbMake(
        name=name_clean,
        sort_weight=int(sort_weight or 0),
        is_active=True,
        created_at=_now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raced = (
            db.query(CustomsDbMake)
            .filter(func.lower(CustomsDbMake.name) == name_clean.lower())
            .first()
        )
        if raced is not None:
            return raced
        raise ValueError("Такая марка уже есть") from exc
    db.refresh(row)
    return row


def delete_make(db: Session, make_id: int) -> None:
    row = db.query(CustomsDbMake).filter(CustomsDbMake.id == make_id).first()
    if row is None:
        raise ValueError("Марка не найдена")
    db.delete(row)
    db.commit()


# —— Models ——


def list_models(db: Session, make_id: int, *, active_only: bool = False) -> list[CustomsDbModel]:
    q = db.query(CustomsDbModel).filter(CustomsDbModel.make_id == make_id)
    if active_only:
        q = q.filter(CustomsDbModel.is_active.is_(True))
    return q.order_by(desc(CustomsDbModel.sort_weight), asc(CustomsDbModel.name), asc(CustomsDbModel.id)).all()


def create_model(db: Session, *, make_id: int, name: str, sort_weight: int = 0) -> CustomsDbModel:
    make = db.query(CustomsDbMake).filter(CustomsDbMake.id == make_id).first()
    if make is None:
        raise ValueError("Сначала выберите марку — обновите страницу")
    name_clean = _clean_name(name, "модель")
    existing = (
        db.query(CustomsDbModel)
        .filter(
            CustomsDbModel.make_id == make_id,
            func.lower(CustomsDbModel.name) == name_clean.lower(),
        )
        .first()
    )
    if existing is not None:
        # Idempotent: same name again (or double-click) returns the existing row.
        return existing
    row = CustomsDbModel(
        make_id=make_id,
        name=name_clean,
        sort_weight=int(sort_weight or 0),
        is_active=True,
        created_at=_now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raced = (
            db.query(CustomsDbModel)
            .filter(
                CustomsDbModel.make_id == make_id,
                func.lower(CustomsDbModel.name) == name_clean.lower(),
            )
            .first()
        )
        if raced is not None:
            return raced
        detail = str(getattr(exc, "orig", exc))
        if "foreign key" in detail.lower():
            raise ValueError("Марка не найдена — обновите страницу и выберите марку снова") from exc
        raise ValueError(f"Не удалось сохранить модель «{name_clean}»") from exc
    db.refresh(row)
    return row


def delete_model(db: Session, model_id: int) -> None:
    row = db.query(CustomsDbModel).filter(CustomsDbModel.id == model_id).first()
    if row is None:
        raise ValueError("Модель не найдена")
    db.delete(row)
    db.commit()


# —— Liters ——


def list_liters(db: Session, model_id: int, *, active_only: bool = False) -> list[CustomsDbEngineLiter]:
    q = db.query(CustomsDbEngineLiter).filter(CustomsDbEngineLiter.model_id == model_id)
    if active_only:
        q = q.filter(CustomsDbEngineLiter.is_active.is_(True))
    return q.order_by(
        desc(CustomsDbEngineLiter.sort_weight),
        asc(CustomsDbEngineLiter.liters),
        asc(CustomsDbEngineLiter.id),
    ).all()


def create_liter(db: Session, *, model_id: int, liters: float, sort_weight: int = 0) -> CustomsDbEngineLiter:
    model = db.query(CustomsDbModel).filter(CustomsDbModel.id == model_id).first()
    if model is None:
        raise ValueError("Сначала выберите модель — обновите страницу")
    liters_val = _parse_liters(liters)
    existing = (
        db.query(CustomsDbEngineLiter)
        .filter(
            CustomsDbEngineLiter.model_id == model_id,
            CustomsDbEngineLiter.liters == liters_val,
        )
        .first()
    )
    if existing is not None:
        return existing
    row = CustomsDbEngineLiter(
        model_id=model_id,
        liters=liters_val,
        sort_weight=int(sort_weight or 0),
        is_active=True,
        created_at=_now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raced = (
            db.query(CustomsDbEngineLiter)
            .filter(
                CustomsDbEngineLiter.model_id == model_id,
                CustomsDbEngineLiter.liters == liters_val,
            )
            .first()
        )
        if raced is not None:
            return raced
        raise ValueError("Такой объём в литрах уже есть у этой модели") from exc
    db.refresh(row)
    return row


def delete_liter(db: Session, liter_id: int) -> None:
    row = db.query(CustomsDbEngineLiter).filter(CustomsDbEngineLiter.id == liter_id).first()
    if row is None:
        raise ValueError("Объём не найден")
    db.delete(row)
    db.commit()


# —— Exact cc ——


def list_ccs(db: Session, liter_id: int, *, active_only: bool = False) -> list[CustomsDbEngineCc]:
    q = db.query(CustomsDbEngineCc).filter(CustomsDbEngineCc.liter_id == liter_id)
    if active_only:
        q = q.filter(CustomsDbEngineCc.is_active.is_(True))
    return q.order_by(
        desc(CustomsDbEngineCc.sort_weight),
        asc(CustomsDbEngineCc.engine_cc),
        asc(CustomsDbEngineCc.id),
    ).all()


def create_cc(
    db: Session,
    *,
    liter_id: int,
    engine_cc: int,
    power_hp: float | None = None,
    notes: str | None = None,
    sort_weight: int = 0,
) -> CustomsDbEngineCc:
    liter = db.query(CustomsDbEngineLiter).filter(CustomsDbEngineLiter.id == liter_id).first()
    if liter is None:
        raise ValueError("Сначала выберите объём в литрах — обновите страницу")
    cc_val = _parse_cc(engine_cc)
    existing = (
        db.query(CustomsDbEngineCc)
        .filter(
            CustomsDbEngineCc.liter_id == liter_id,
            CustomsDbEngineCc.engine_cc == cc_val,
        )
        .first()
    )
    if existing is not None:
        return existing
    hp = None
    if power_hp is not None and power_hp != "":
        try:
            hp = float(power_hp)
        except (TypeError, ValueError) as exc:
            raise ValueError("Мощность должна быть числом") from exc
        if hp <= 0:
            raise ValueError("Мощность должна быть больше 0")
    row = CustomsDbEngineCc(
        liter_id=liter_id,
        engine_cc=cc_val,
        power_hp=hp,
        notes=(notes or "").strip() or None,
        sort_weight=int(sort_weight or 0),
        is_active=True,
        created_at=_now(),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raced = (
            db.query(CustomsDbEngineCc)
            .filter(
                CustomsDbEngineCc.liter_id == liter_id,
                CustomsDbEngineCc.engine_cc == cc_val,
            )
            .first()
        )
        if raced is not None:
            return raced
        raise ValueError("Такой объём в см³ уже есть") from exc
    db.refresh(row)
    return row


def delete_cc(db: Session, cc_id: int) -> None:
    row = db.query(CustomsDbEngineCc).filter(CustomsDbEngineCc.id == cc_id).first()
    if row is None:
        raise ValueError("Запись см³ не найдена")
    db.delete(row)
    db.commit()


def get_cc(db: Session, cc_id: int) -> CustomsDbEngineCc | None:
    return (
        db.query(CustomsDbEngineCc)
        .options(
            joinedload(CustomsDbEngineCc.liter)
            .joinedload(CustomsDbEngineLiter.model)
            .joinedload(CustomsDbModel.make)
        )
        .filter(CustomsDbEngineCc.id == cc_id)
        .first()
    )


def public_make_names(db: Session) -> list[str]:
    return [row.name for row in list_makes(db, active_only=True)]


def public_models_for_make_name(db: Session, make_name: str) -> list[CustomsDbModel]:
    key = (make_name or "").strip().lower()
    if not key:
        return []
    make = (
        db.query(CustomsDbMake)
        .filter(CustomsDbMake.is_active.is_(True), func.lower(CustomsDbMake.name) == key)
        .first()
    )
    if make is None:
        return []
    return list_models(db, make.id, active_only=True)


def cc_label(row: CustomsDbEngineCc) -> str:
    liter = row.liter
    model = liter.model if liter else None
    make = model.make if model else None
    parts = []
    if make:
        parts.append(make.name)
    if model:
        parts.append(model.name)
    if liter:
        parts.append(f"{float(liter.liters):g} л")
    parts.append(f"{row.engine_cc} см³")
    if row.power_hp:
        parts.append(f"{float(row.power_hp):g} л.с.")
    return " · ".join(parts)
