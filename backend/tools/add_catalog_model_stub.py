"""Insert a catalog model stub without modification specs."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.db import SessionLocal
from app.models import CatalogItem


def main() -> None:
    parser = argparse.ArgumentParser(description="Add catalog model stub without characteristics")
    parser.add_argument("--make", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--source-external-id", default=None)
    args = parser.parse_args()

    make = args.make.strip()
    model = args.model.strip()
    source_url = (args.source_url or "").strip() or None
    source_external_id = (args.source_external_id or "").strip() or None
    if not source_external_id and source_url:
        source_external_id = f"model-{source_url.rstrip('/').rsplit('/', 1)[-1]}"

    db = SessionLocal()
    try:
        existing = (
            db.query(CatalogItem)
            .filter(CatalogItem.make == make, CatalogItem.model == model)
            .first()
        )
        if existing:
            print(
                f"exists: id={existing.id} make={existing.make} model={existing.model} "
                f"generation={existing.generation}"
            )
            return

        item = CatalogItem(
            make=make,
            model=model,
            generation=None,
            year_from=None,
            year_to=None,
            source_site="av.by",
            source_url=source_url,
            source_external_id=source_external_id,
            raw_specs={"stub": True, "note": "model without characteristics"},
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        print(f"created: id={item.id} make={item.make} model={item.model} source_url={item.source_url}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
