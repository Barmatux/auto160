#!/usr/bin/env python3
"""Import internal catalog ratings from JSON or CSV into catalog_items.rating.

The rating is stored per catalog item row and is visible in the catalog UI for admin users only.

JSON format (array of objects):
[
  {"source_url": "https://av.by/catalog/renault_captur_ii-2019", "rating": 1},
  {"make": "MINI", "rating": 1},
  {"make": "BMW", "model": "X1", "rating": 8.5}
]

CSV format (header row required):
make,model,generation,rating
BMW,X1,,8.5
Renault,Captur,II,7.2

Matching rules:
- id: updates exactly one catalog item
- make + model (+ optional generation): updates all matching catalog_items
- make/model comparison is case-insensitive; generation is exact when provided
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from sqlalchemy import func, or_

from app.db import SessionLocal
from app.models import CatalogItem


def _normalize(value: str | None) -> str:
    return (value or "").strip()


def _parse_rating(raw) -> float:
    if raw is None or raw == "":
        raise ValueError("rating is required")
    return float(str(raw).replace(",", "."))


def _load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("items"), list):
        return payload["items"]
    raise ValueError("JSON must be an array or an object with an 'items' array")


def _normalize_catalog_url(value: str | None) -> str:
    url = (value or "").strip()
    if not url:
        return ""
    if url.startswith("catalog/"):
        url = f"https://av.by/{url}"
    elif not url.startswith("http"):
        url = f"https://av.by/catalog/{url.lstrip('/')}"
    url = url.split("#", 1)[0].rstrip("/")
    while url.endswith("-"):
        url = url[:-1]
    while url.endswith("..."):
        url = url[:-3].rstrip("-")
    return url


def _match_items(db, row: dict) -> list[CatalogItem]:
    if row.get("id") is not None and str(row.get("id")).strip() != "":
        item = db.query(CatalogItem).filter(CatalogItem.id == int(row["id"])).first()
        return [item] if item else []

    source_url = _normalize_catalog_url(row.get("source_url"))
    if source_url:
        slug = source_url.rsplit("/catalog/", 1)[-1]
        return (
            db.query(CatalogItem)
            .filter(
                CatalogItem.source_site == "av.by",
                or_(
                    CatalogItem.source_url.like(f"{source_url}%"),
                    CatalogItem.source_url.like(f"%/catalog/{slug}%"),
                ),
            )
            .order_by(CatalogItem.id.asc())
            .all()
        )

    make = _normalize(row.get("make"))
    model = _normalize(row.get("model"))
    generation = _normalize(row.get("generation"))
    if make and not model:
        return (
            db.query(CatalogItem)
            .filter(func.lower(CatalogItem.make) == make.lower())
            .order_by(CatalogItem.id.asc())
            .all()
        )
    if not make or not model:
        raise ValueError("each row needs id, source_url, make-only, or both make and model")

    query = db.query(CatalogItem).filter(
        func.lower(CatalogItem.make) == make.lower(),
        func.lower(CatalogItem.model) == model.lower(),
    )
    if generation:
        query = query.filter(CatalogItem.generation == generation)
    return query.order_by(CatalogItem.id.asc()).all()


def import_ratings(path: Path, *, dry_run: bool = False) -> dict:
    rows = _load_rows(path)
    db = SessionLocal()
    updated_items = 0
    matched_rows = 0
    skipped_rows = 0
    details: list[str] = []

    try:
        for index, row in enumerate(rows, start=1):
            try:
                rating = _parse_rating(row.get("rating"))
            except ValueError as exc:
                skipped_rows += 1
                details.append(f"row {index}: skipped ({exc})")
                continue

            try:
                items = _match_items(db, row)
            except ValueError as exc:
                skipped_rows += 1
                details.append(f"row {index}: skipped ({exc})")
                continue

            if not items:
                skipped_rows += 1
                label = row.get("id") or row.get("source_url") or f"{row.get('make')} {row.get('model')}"
                details.append(f"row {index}: no matches for {label}")
                continue

            matched_rows += 1
            for item in items:
                item.rating = rating
                updated_items += 1

        if dry_run:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    return {
        "source_rows": len(rows),
        "matched_rows": matched_rows,
        "updated_items": updated_items,
        "skipped_rows": skipped_rows,
        "dry_run": dry_run,
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import internal catalog item ratings")
    parser.add_argument(
        "file",
        nargs="?",
        default="data/catalog_ratings.json",
        help="Path to JSON or CSV file (default: data/catalog_ratings.json)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Match and count without saving")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    result = import_ratings(path, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["details"]:
        print("\nDetails:")
        for line in result["details"][:50]:
            print(f"- {line}")
        if len(result["details"]) > 50:
            print(f"... and {len(result['details']) - 50} more")


if __name__ == "__main__":
    main()
