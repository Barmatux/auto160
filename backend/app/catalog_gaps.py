"""Persist catalog holes reported by internal match consumers."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.catalog_match import CatalogMatchInput
from app.models import CatalogGap


def enqueue_catalog_gap(
    db: Session,
    candidate: CatalogMatchInput,
    *,
    source: str = "eu2",
    notes: str | None = None,
    commit: bool = False,
) -> CatalogGap:
    """Insert or refresh an open gap for the same source + external_ref/make/model signature."""
    now = datetime.utcnow()
    existing = _find_open_gap(db, source=source, candidate=candidate)
    if existing is not None:
        existing.generation = candidate.generation
        existing.year = candidate.year
        existing.body_type = candidate.body_type
        existing.fuel_type = candidate.fuel_type
        existing.engine_power_hp = candidate.engine_power_hp
        existing.engine_volume_l = candidate.engine_volume_l
        existing.drivetrain = candidate.drivetrain
        existing.transmission = candidate.transmission
        existing.source_external_id = candidate.source_external_id
        existing.payload = _payload_dict(candidate)
        if notes:
            existing.notes = notes
        existing.updated_at = now
        gap = existing
    else:
        gap = CatalogGap(
            source=source,
            external_ref=candidate.external_ref,
            make=(candidate.make or "").strip(),
            model=(candidate.model or "").strip(),
            generation=candidate.generation,
            year=candidate.year,
            body_type=candidate.body_type,
            fuel_type=candidate.fuel_type,
            engine_power_hp=candidate.engine_power_hp,
            engine_volume_l=candidate.engine_volume_l,
            drivetrain=candidate.drivetrain,
            transmission=candidate.transmission,
            source_external_id=candidate.source_external_id,
            payload=_payload_dict(candidate),
            status="open",
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        db.add(gap)

    if commit:
        db.commit()
        db.refresh(gap)
    else:
        db.flush()
    return gap


def _payload_dict(candidate: CatalogMatchInput) -> dict:
    return {
        "external_ref": candidate.external_ref,
        "make": candidate.make,
        "model": candidate.model,
        "generation": candidate.generation,
        "year": candidate.year,
        "body_type": candidate.body_type,
        "fuel_type": candidate.fuel_type,
        "engine_power_hp": candidate.engine_power_hp,
        "engine_volume_l": candidate.engine_volume_l,
        "drivetrain": candidate.drivetrain,
        "transmission": candidate.transmission,
        "source_external_id": candidate.source_external_id,
    }


def _find_open_gap(db: Session, *, source: str, candidate: CatalogMatchInput) -> CatalogGap | None:
    query = db.query(CatalogGap).filter(CatalogGap.source == source, CatalogGap.status == "open")
    if candidate.external_ref:
        return query.filter(CatalogGap.external_ref == candidate.external_ref).first()
    return (
        query.filter(
            CatalogGap.make == (candidate.make or "").strip(),
            CatalogGap.model == (candidate.model or "").strip(),
            CatalogGap.generation == candidate.generation,
            CatalogGap.engine_power_hp == candidate.engine_power_hp,
            CatalogGap.source_external_id == candidate.source_external_id,
        )
        .order_by(CatalogGap.id.desc())
        .first()
    )
