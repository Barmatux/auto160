"""Match external catalog candidates (eu2 etc.) to CatalogItem rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.catalog_visibility import apply_visible_catalog_filter
from app.listing_catalog_link import (
    MIN_LINK_SCORE,
    body_types_compatible,
    canonical_model_name,
    normalize_match_text,
)
from app.models import CatalogItem

MatchReason = Literal["exact_external_id", "best_fuzzy", "not_found"]


@dataclass(frozen=True)
class CatalogMatchInput:
    """Modification-level candidate (same grain as CatalogItem)."""

    make: str
    model: str
    generation: str | None = None
    year: int | None = None
    body_type: str | None = None
    fuel_type: str | None = None
    engine_power_hp: int | None = None
    engine_volume_l: float | None = None
    drivetrain: str | None = None
    transmission: str | None = None
    source_external_id: str | None = None
    cover_photo_url: str | None = None
    external_ref: str | None = None


@dataclass(frozen=True)
class CatalogMatchOutcome:
    external_ref: str | None
    matched_catalog_item_id: int | None
    match_confidence: int
    reason: MatchReason
    make: str
    model: str


def score_catalog_match(
    candidate: CatalogMatchInput,
    item: CatalogItem,
    *,
    require_cover: bool = False,
) -> int:
    if require_cover and not candidate.cover_photo_url:
        return -1
    if normalize_match_text(candidate.make) != normalize_match_text(item.make):
        return -1
    if canonical_model_name(candidate.model) != canonical_model_name(item.model):
        return -1
    if not body_types_compatible(item.body_type, candidate.body_type):
        return -1

    score = 10
    if item.body_type and candidate.body_type:
        if normalize_match_text(item.body_type) == normalize_match_text(candidate.body_type):
            score += 40
        else:
            score += 25
    if item.generation and candidate.generation:
        if normalize_match_text(item.generation) == normalize_match_text(candidate.generation):
            score += 20
        elif normalize_match_text(candidate.generation) in normalize_match_text(item.generation):
            score += 10
    if item.year_from is not None and candidate.year is not None:
        year_to = item.year_to if item.year_to is not None else item.year_from
        if item.year_from <= candidate.year <= year_to:
            score += 15
        elif abs(candidate.year - item.year_from) <= 1 or abs(candidate.year - year_to) <= 1:
            score += 5
    if item.engine_power_hp is not None and candidate.engine_power_hp is not None:
        diff = abs(item.engine_power_hp - candidate.engine_power_hp)
        if diff <= 5:
            score += 25
        elif diff <= 15:
            score += 12
        elif diff <= 30:
            score += 5
    if item.fuel_type and candidate.fuel_type:
        if normalize_match_text(item.fuel_type) == normalize_match_text(candidate.fuel_type):
            score += 8
    if item.engine_volume_l is not None and candidate.engine_volume_l is not None:
        if abs(float(item.engine_volume_l) - float(candidate.engine_volume_l)) <= 0.15:
            score += 8
    if item.drivetrain and candidate.drivetrain:
        if normalize_match_text(item.drivetrain) == normalize_match_text(candidate.drivetrain):
            score += 5
    if item.transmission and candidate.transmission:
        if normalize_match_text(item.transmission) == normalize_match_text(candidate.transmission):
            score += 5
    return score


def find_best_catalog_match(
    candidate: CatalogMatchInput,
    catalog_items: list[CatalogItem],
) -> tuple[CatalogItem | None, int]:
    best_item: CatalogItem | None = None
    best_score = -1
    for item in catalog_items:
        score = score_catalog_match(candidate, item)
        if score < MIN_LINK_SCORE:
            continue
        if score > best_score or (score == best_score and best_item and item.id < best_item.id):
            best_score = score
            best_item = item
    return best_item, best_score if best_item else 0


def _candidates_for_input(db: Session, candidate: CatalogMatchInput) -> list[CatalogItem]:
    make = (candidate.make or "").strip()
    model = canonical_model_name(candidate.model)
    if not make or not model:
        return []
    return apply_visible_catalog_filter(
        db.query(CatalogItem)
        .filter(
            CatalogItem.make.ilike(make),
            CatalogItem.model == model,
            or_(CatalogItem.engine_power_hp.is_(None), CatalogItem.engine_power_hp <= 160),
        )
        .order_by(CatalogItem.year_from.desc(), CatalogItem.id.asc())
    ).all()


def match_catalog_candidate(db: Session, candidate: CatalogMatchInput) -> CatalogMatchOutcome:
    external_id = (candidate.source_external_id or "").strip()
    if external_id:
        exact = (
            apply_visible_catalog_filter(
                db.query(CatalogItem).filter(CatalogItem.source_external_id == external_id)
            )
            .order_by(CatalogItem.id.asc())
            .first()
        )
        if exact is not None:
            return CatalogMatchOutcome(
                external_ref=candidate.external_ref,
                matched_catalog_item_id=exact.id,
                match_confidence=100,
                reason="exact_external_id",
                make=candidate.make,
                model=candidate.model,
            )

    best, score = find_best_catalog_match(candidate, _candidates_for_input(db, candidate))
    if best is None:
        return CatalogMatchOutcome(
            external_ref=candidate.external_ref,
            matched_catalog_item_id=None,
            match_confidence=0,
            reason="not_found",
            make=candidate.make,
            model=candidate.model,
        )
    return CatalogMatchOutcome(
        external_ref=candidate.external_ref,
        matched_catalog_item_id=best.id,
        match_confidence=score,
        reason="best_fuzzy",
        make=candidate.make,
        model=candidate.model,
    )


def match_catalog_candidates(db: Session, candidates: list[CatalogMatchInput]) -> list[CatalogMatchOutcome]:
    return [match_catalog_candidate(db, row) for row in candidates]


def catalog_item_public_dict(item: CatalogItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "make": item.make,
        "model": item.model,
        "generation": item.generation,
        "year_from": item.year_from,
        "year_to": item.year_to,
        "body_type": item.body_type,
        "fuel_type": item.fuel_type,
        "engine_power_hp": item.engine_power_hp,
        "engine_volume_l": float(item.engine_volume_l) if item.engine_volume_l is not None else None,
        "drivetrain": item.drivetrain,
        "transmission": item.transmission,
        "source_site": item.source_site,
        "source_external_id": item.source_external_id,
        "source_url": item.source_url,
        "rating": float(item.rating) if item.rating is not None else None,
        "has_7_seats": bool(item.has_7_seats),
        "hidden_from_catalog": bool(item.hidden_from_catalog),
    }
