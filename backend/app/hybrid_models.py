"""Detect hybrid and plug-in hybrid make/model pairs from catalog and listings."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.fuel_type_labels import HYBRID_MARKERS, fuel_labels_from_raw_specs, normalize_fuel_type_key, resolved_catalog_fuel_type
from app.models import CarListing, CatalogItem, ListingStatus

PLUGIN_HYBRID_MARKERS = ("phev", "plug-in", "plugin", "плагин")
HYBRID_TYPE_LABEL = "Гибрид (HEV/MHEV)"
PLUGIN_HYBRID_TYPE_LABEL = "Плагин-гибрид (PHEV)"


@dataclass(frozen=True)
class HybridModelEntry:
    make: str
    model: str
    engine_type: str


def classify_hybrid_engine_type(*labels: str | None) -> str | None:
    for label in labels:
        if not label:
            continue
        key = normalize_fuel_type_key(label)
        if not key:
            continue
        if any(marker in key for marker in PLUGIN_HYBRID_MARKERS):
            return PLUGIN_HYBRID_TYPE_LABEL
    for label in labels:
        if not label:
            continue
        key = normalize_fuel_type_key(label)
        if any(marker in key for marker in HYBRID_MARKERS):
            return HYBRID_TYPE_LABEL
    return None


def _merge_engine_type(current: str | None, new: str | None) -> str | None:
    if new is None:
        return current
    if current is None:
        return new
    if current == PLUGIN_HYBRID_TYPE_LABEL or new == PLUGIN_HYBRID_TYPE_LABEL:
        return PLUGIN_HYBRID_TYPE_LABEL
    return current


def collect_hybrid_models(db: Session) -> dict[str, list[HybridModelEntry]]:
    grouped: dict[tuple[str, str], str] = {}

    catalog_rows = (
        db.query(CatalogItem)
        .filter(CatalogItem.source_site == "av.by", CatalogItem.make.isnot(None), CatalogItem.model.isnot(None))
        .order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.id.asc())
        .all()
    )
    for item in catalog_rows:
        labels = [
            item.fuel_type,
            resolved_catalog_fuel_type(item.fuel_type, item.raw_specs),
            *fuel_labels_from_raw_specs(item.raw_specs),
        ]
        engine_type = classify_hybrid_engine_type(*labels)
        if not engine_type:
            continue
        key = (item.make.strip(), item.model.strip())
        grouped[key] = _merge_engine_type(grouped.get(key), engine_type) or engine_type

    listing_rows = (
        db.query(CarListing)
        .filter(
            CarListing.status == ListingStatus.published,
            CarListing.brand.isnot(None),
            CarListing.model.isnot(None),
        )
        .order_by(CarListing.brand.asc(), CarListing.model.asc(), CarListing.id.asc())
        .all()
    )
    for listing in listing_rows:
        engine_type = classify_hybrid_engine_type(listing.engine_type, listing.description)
        if not engine_type:
            continue
        key = (listing.brand.strip(), listing.model.strip())
        grouped[key] = _merge_engine_type(grouped.get(key), engine_type) or engine_type

    by_type: dict[str, list[HybridModelEntry]] = {
        HYBRID_TYPE_LABEL: [],
        PLUGIN_HYBRID_TYPE_LABEL: [],
    }
    for (make, model), engine_type in sorted(grouped.items(), key=lambda row: (row[0][0].lower(), row[0][1].lower())):
        by_type[engine_type].append(HybridModelEntry(make=make, model=model, engine_type=engine_type))
    return by_type
