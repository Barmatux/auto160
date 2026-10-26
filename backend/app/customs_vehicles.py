"""CRUD helpers for admin customs vehicle specs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session

from app.models import CustomsVehicleSpec


def list_customs_vehicle_specs(
    db: Session,
    *,
    active_only: bool = False,
) -> list[CustomsVehicleSpec]:
    q = db.query(CustomsVehicleSpec)
    if active_only:
        q = q.filter(CustomsVehicleSpec.is_active.is_(True))
    return (
        q.order_by(
            desc(CustomsVehicleSpec.sort_weight),
            asc(CustomsVehicleSpec.make),
            asc(CustomsVehicleSpec.model),
            asc(CustomsVehicleSpec.engine_cc),
            asc(CustomsVehicleSpec.id),
        ).all()
    )


def list_makes(db: Session) -> list[str]:
    rows = (
        db.query(CustomsVehicleSpec.make)
        .filter(CustomsVehicleSpec.is_active.is_(True))
        .distinct()
        .order_by(asc(CustomsVehicleSpec.make))
        .all()
    )
    return [r[0] for r in rows if r[0]]


def list_models_for_make(db: Session, make: str) -> list[CustomsVehicleSpec]:
    make_key = (make or "").strip()
    if not make_key:
        return []
    return (
        db.query(CustomsVehicleSpec)
        .filter(
            CustomsVehicleSpec.is_active.is_(True),
            func.lower(CustomsVehicleSpec.make) == make_key.lower(),
        )
        .order_by(
            desc(CustomsVehicleSpec.sort_weight),
            asc(CustomsVehicleSpec.model),
            asc(CustomsVehicleSpec.engine_cc),
            asc(CustomsVehicleSpec.id),
        )
        .all()
    )


def get_customs_vehicle_spec(db: Session, spec_id: int) -> CustomsVehicleSpec | None:
    return db.query(CustomsVehicleSpec).filter(CustomsVehicleSpec.id == spec_id).first()


def create_customs_vehicle_spec(
    db: Session,
    *,
    make: str,
    model: str,
    engine_cc: int,
    power_hp: float,
    generation: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    engine_kind: str = "ice",
    fuel_label: str | None = None,
    notes: str | None = None,
    is_active: bool = True,
    sort_weight: int = 0,
) -> CustomsVehicleSpec:
    make_clean = (make or "").strip()
    model_clean = (model or "").strip()
    if not make_clean or not model_clean:
        raise ValueError("Укажите марку и модель")
    if engine_cc <= 0 and engine_kind != "electric":
        raise ValueError("Объём двигателя должен быть больше 0")
    if power_hp <= 0:
        raise ValueError("Мощность должна быть больше 0")
    if engine_kind not in {"ice", "electric"}:
        raise ValueError("Тип двигателя: ice или electric")
    if year_from and year_to and year_from > year_to:
        raise ValueError("Год «с» не может быть больше года «по»")

    now = datetime.utcnow()
    row = CustomsVehicleSpec(
        make=make_clean,
        model=model_clean,
        generation=(generation or "").strip() or None,
        year_from=year_from,
        year_to=year_to,
        engine_cc=int(engine_cc),
        power_hp=float(power_hp),
        engine_kind=engine_kind,
        fuel_label=(fuel_label or "").strip() or None,
        notes=(notes or "").strip() or None,
        is_active=bool(is_active),
        sort_weight=int(sort_weight or 0),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_customs_vehicle_spec(
    db: Session,
    spec_id: int,
    **fields: object,
) -> CustomsVehicleSpec:
    row = get_customs_vehicle_spec(db, spec_id)
    if row is None:
        raise ValueError("Запись не найдена")

    if "make" in fields and fields["make"] is not None:
        make_clean = str(fields["make"]).strip()
        if not make_clean:
            raise ValueError("Укажите марку")
        row.make = make_clean
    if "model" in fields and fields["model"] is not None:
        model_clean = str(fields["model"]).strip()
        if not model_clean:
            raise ValueError("Укажите модель")
        row.model = model_clean
    if "generation" in fields:
        gen = fields["generation"]
        row.generation = (str(gen).strip() if gen else None) or None
    if "year_from" in fields:
        row.year_from = fields["year_from"]  # type: ignore[assignment]
    if "year_to" in fields:
        row.year_to = fields["year_to"]  # type: ignore[assignment]
    if "engine_cc" in fields and fields["engine_cc"] is not None:
        row.engine_cc = int(fields["engine_cc"])  # type: ignore[arg-type]
    if "power_hp" in fields and fields["power_hp"] is not None:
        row.power_hp = float(fields["power_hp"])  # type: ignore[arg-type]
    if "engine_kind" in fields and fields["engine_kind"] is not None:
        kind = str(fields["engine_kind"])
        if kind not in {"ice", "electric"}:
            raise ValueError("Тип двигателя: ice или electric")
        row.engine_kind = kind
    if "fuel_label" in fields:
        fl = fields["fuel_label"]
        row.fuel_label = (str(fl).strip() if fl else None) or None
    if "notes" in fields:
        n = fields["notes"]
        row.notes = (str(n).strip() if n else None) or None
    if "is_active" in fields and fields["is_active"] is not None:
        row.is_active = bool(fields["is_active"])
    if "sort_weight" in fields and fields["sort_weight"] is not None:
        row.sort_weight = int(fields["sort_weight"])  # type: ignore[arg-type]

    if row.year_from and row.year_to and row.year_from > row.year_to:
        raise ValueError("Год «с» не может быть больше года «по»")
    if row.engine_cc <= 0 and row.engine_kind != "electric":
        raise ValueError("Объём двигателя должен быть больше 0")
    if row.power_hp <= 0:
        raise ValueError("Мощность должна быть больше 0")

    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def delete_customs_vehicle_spec(db: Session, spec_id: int) -> None:
    row = get_customs_vehicle_spec(db, spec_id)
    if row is None:
        raise ValueError("Запись не найдена")
    db.delete(row)
    db.commit()


def search_customs_vehicle_specs(db: Session, query: str, *, limit: int = 40) -> list[CustomsVehicleSpec]:
    q = (query or "").strip()
    if not q:
        return list_customs_vehicle_specs(db, active_only=True)[:limit]
    like = f"%{q}%"
    return (
        db.query(CustomsVehicleSpec)
        .filter(
            CustomsVehicleSpec.is_active.is_(True),
            or_(
                CustomsVehicleSpec.make.ilike(like),
                CustomsVehicleSpec.model.ilike(like),
                CustomsVehicleSpec.generation.ilike(like),
            ),
        )
        .order_by(
            desc(CustomsVehicleSpec.sort_weight),
            asc(CustomsVehicleSpec.make),
            asc(CustomsVehicleSpec.model),
        )
        .limit(limit)
        .all()
    )
