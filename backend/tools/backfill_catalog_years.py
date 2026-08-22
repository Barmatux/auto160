#!/usr/bin/env python3
"""Backfill catalog_items.year_from/year_to from av.by slugs and URLs already stored in DB."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.catalog_generation_years import sync_generation_years_from_sources
from app.catalog_ratings import generation_key, matching_catalog_items
from app.db import SessionLocal
from app.models import CatalogItem


def _grouped_generations(db):
    return (
        db.query(CatalogItem.make, CatalogItem.model, CatalogItem.generation)
        .filter(CatalogItem.source_site == "av.by")
        .group_by(CatalogItem.make, CatalogItem.model, CatalogItem.generation)
        .order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.generation.asc())
        .all()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill catalog production years from stored av.by metadata")
    parser.add_argument("--dry-run", action="store_true", help="Only print planned updates")
    parser.add_argument("--missing-only", action="store_true", default=True, help="Update groups with missing years (default)")
    parser.add_argument("--all", dest="missing_only", action="store_false", help="Re-sync all generations")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        updated_groups = 0
        updated_items = 0
        skipped = 0
        for row in _grouped_generations(db):
            make = (row.make or "").strip()
            model = (row.model or "").strip()
            generation = generation_key(row.generation)
            items = matching_catalog_items(db, make=make, model=model, generation=generation)
            if not items:
                continue
            if args.missing_only and any(item.year_from is not None or item.year_to is not None for item in items):
                skipped += 1
                continue
            _, count, label = sync_generation_years_from_sources(
                db,
                make=make,
                model=model,
                generation=generation,
            )
            if count == 0:
                skipped += 1
                print(f"skip: {make} {model} · {generation or '—'} — years not found in stored av.by data")
                continue
            updated_groups += 1
            updated_items += count
            print(f"ok: {make} {model} · {generation or '—'} -> {label} ({count} items)")
        if args.dry_run:
            db.rollback()
            print(f"dry-run: groups={updated_groups} items={updated_items} skipped={skipped}")
            return
        db.commit()
        print(f"done: groups={updated_groups} items={updated_items} skipped={skipped}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
