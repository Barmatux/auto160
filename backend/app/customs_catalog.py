"""Customs calculator cascade backed by the main Auto160 catalog (CatalogItem)."""

from __future__ import annotations

from sqlalchemy import asc, func
from sqlalchemy.orm import Session

from app.catalog_engine_cc import resolve_engine_capacity_cc
from app.catalog_visibility import apply_visible_catalog_filter
from app.fuel_type_labels import (
    FUEL_GROUP_ELECTRIC,
    classify_fuel_type,
    resolved_catalog_fuel_type,
)
from app.models import CatalogItem


def _base_catalog_query(db: Session):
    q = db.query(CatalogItem).filter(
        CatalogItem.source_site == "av.by",
        CatalogItem.make.isnot(None),
        CatalogItem.model.isnot(None),
        CatalogItem.customs_calc.is_(True),
    )
    return apply_visible_catalog_filter(q, include_hidden=False)


def list_makes(db: Session) -> list[str]:
    rows = (
        _base_catalog_query(db)
        .with_entities(CatalogItem.make)
        .distinct()
        .order_by(asc(CatalogItem.make))
        .all()
    )
    return [name for (name,) in rows if (name or "").strip()]


PREFERENTIAL_HP_MAX = 160


def list_models(db: Session, make: str) -> list[dict]:
    key = (make or "").strip()
    if not key:
        return []
    rows = (
        _base_catalog_query(db)
        .filter(func.lower(CatalogItem.make) == key.lower())
        .with_entities(
            CatalogItem.model,
            func.max(CatalogItem.engine_power_hp).label("hp_max"),
        )
        .group_by(CatalogItem.model)
        .order_by(asc(CatalogItem.model))
        .all()
    )
    result: list[dict] = []
    for name, hp_max in rows:
        cleaned = (name or "").strip()
        if not cleaned:
            continue
        # Model is preferential when every known catalog hp is ≤160.
        under_160 = hp_max is not None and int(hp_max) <= PREFERENTIAL_HP_MAX
        result.append({"name": cleaned, "under_160": under_160})
    return result


def engine_cc_from_item(item: CatalogItem) -> int | None:
    return resolve_engine_capacity_cc(
        engine_capacity_cc=item.engine_capacity_cc,
        raw_specs=item.raw_specs if isinstance(item.raw_specs, dict) else None,
        engine_volume_l=item.engine_volume_l,
    )


def power_hp_from_item(item: CatalogItem) -> float | None:
    raw = item.raw_specs if isinstance(item.raw_specs, dict) else {}
    detail = raw.get("modification_detail") if isinstance(raw, dict) else None
    if isinstance(detail, dict):
        for key in ("maxPowerHP", "enginePower"):
            value = str(detail.get(key) or "").strip()
            if value.isdigit() and int(value) > 0:
                return float(value)
    if item.engine_power_hp is not None and int(item.engine_power_hp) > 0:
        return float(item.engine_power_hp)
    return None


def engine_kind_from_item(item: CatalogItem) -> str:
    raw = item.raw_specs if isinstance(item.raw_specs, dict) else {}
    fuel = resolved_catalog_fuel_type(item.fuel_type, raw) or item.fuel_type
    label = classify_fuel_type(fuel) if fuel else None
    if label == FUEL_GROUP_ELECTRIC:
        return "electric"
    if fuel and "электр" in str(fuel).lower():
        return "electric"
    return "ice"


def _modification_name(item: CatalogItem) -> str:
    raw = item.raw_specs if isinstance(item.raw_specs, dict) else {}
    for key in ("modification_detail", "modification"):
        block = raw.get(key)
        if isinstance(block, dict):
            name = (block.get("name") or "").strip()
            if name:
                return name
    return (item.source_external_id or "").strip()


def motor_label(item: CatalogItem, *, engine_cc: int | None, power_hp: float | None) -> str:
    parts: list[str] = []
    generation = (item.generation or "").strip()
    if generation:
        parts.append(generation)
    mod_name = _modification_name(item)
    if mod_name and mod_name.lower() != generation.lower():
        parts.append(mod_name)
    if engine_cc:
        parts.append(f"{engine_cc} см³")
    elif item.engine_volume_l is not None:
        parts.append(f"{float(item.engine_volume_l):g} л")
    if power_hp:
        parts.append(f"{power_hp:g} л.с.")
    fuel = resolved_catalog_fuel_type(
        item.fuel_type, item.raw_specs if isinstance(item.raw_specs, dict) else None
    )
    label = classify_fuel_type(fuel) if fuel else None
    if label:
        parts.append(label)
    return " · ".join(parts) if parts else f"#{item.id}"


def list_motors(db: Session, make: str, model: str) -> list[dict]:
    make_key = (make or "").strip()
    model_key = (model or "").strip()
    if not make_key or not model_key:
        return []
    items = (
        _base_catalog_query(db)
        .filter(
            func.lower(CatalogItem.make) == make_key.lower(),
            func.lower(CatalogItem.model) == model_key.lower(),
        )
        .order_by(
            asc(CatalogItem.generation),
            asc(CatalogItem.engine_volume_l),
            asc(CatalogItem.engine_power_hp),
            asc(CatalogItem.id),
        )
        .all()
    )
    result: list[dict] = []
    seen: set[tuple] = set()
    for item in items:
        engine_cc = engine_cc_from_item(item)
        power_hp = power_hp_from_item(item)
        # Need at least volume (cc) or electric with power for a usable calc config
        if engine_cc is None and engine_kind_from_item(item) != "electric":
            continue
        if power_hp is None:
            continue
        key = (
            (item.generation or "").strip().lower(),
            _modification_name(item).lower(),
            engine_cc or 0,
            power_hp,
            engine_kind_from_item(item),
        )
        if key in seen:
            continue
        seen.add(key)
        liters = float(item.engine_volume_l) if item.engine_volume_l is not None else (
            round((engine_cc or 0) / 1000, 1) if engine_cc else None
        )
        result.append(
            {
                "id": item.id,
                "generation": (item.generation or "").strip() or None,
                "liters": liters,
                "engine_cc": engine_cc or 0,
                "power_hp": power_hp,
                "engine_kind": engine_kind_from_item(item),
                "under_160": float(power_hp) <= PREFERENTIAL_HP_MAX,
                "label": motor_label(item, engine_cc=engine_cc, power_hp=power_hp),
            }
        )
    return result


def get_item(db: Session, item_id: int) -> CatalogItem | None:
    return db.query(CatalogItem).filter(CatalogItem.id == item_id).first()
