#!/usr/bin/env python3
"""List catalog generations (make/model/generation) without internal rating."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from sqlalchemy import or_

from app.db import SessionLocal
from app.models import CatalogItem


def main() -> None:
    db = SessionLocal()
    rows = (
        db.query(CatalogItem)
        .filter(
            CatalogItem.source_site == "av.by",
            or_(CatalogItem.engine_power_hp.is_(None), CatalogItem.engine_power_hp <= 160),
        )
        .order_by(CatalogItem.make, CatalogItem.model, CatalogItem.generation)
        .all()
    )

    by_generation: dict[tuple[str, str, str], dict] = {}
    for item in rows:
        make = (item.make or "").strip()
        model = (item.model or "").strip()
        generation = (item.generation or "Без поколения").strip()
        if not make or not model:
            continue
        key = (make, model, generation)
        entry = by_generation.setdefault(
            key,
            {
                "make": make,
                "model": model,
                "generation": generation,
                "count": 0,
                "rated_count": 0,
                "source_url": item.source_url,
            },
        )
        entry["count"] += 1
        if item.rating is not None:
            entry["rated_count"] += 1
        if item.source_url and not entry.get("source_url"):
            entry["source_url"] = item.source_url

    unrated = [v for v in by_generation.values() if v["rated_count"] == 0]
    unrated.sort(key=lambda x: (x["make"], x["model"], x["generation"]))

    by_make: dict[str, list[dict]] = defaultdict(list)
    for item in unrated:
        by_make[item["make"]].append(item)

    print(f"TOTAL_GENERATIONS={len(unrated)}")
    print(f"TOTAL_MAKES={len(by_make)}")
    print("---")
    for make in sorted(by_make):
        models = by_make[make]
        print(f"## {make} ({len(models)} поколений)")
        for g in models:
            url = g["source_url"] or ""
            if url and "/modification/" in url:
                url = url.split("/modification/")[0]
            print(f"- {g['model']} | {g['generation']} | mods={g['count']} | {url}")
        print()

    db.close()


if __name__ == "__main__":
    main()
