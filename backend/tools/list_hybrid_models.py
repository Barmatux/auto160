"""List hybrid and plug-in hybrid make/model pairs present on the site."""

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
from app.hybrid_models import HYBRID_TYPE_LABEL, PLUGIN_HYBRID_TYPE_LABEL, collect_hybrid_models


def main() -> None:
    parser = argparse.ArgumentParser(description="List hybrid make/model pairs from catalog and published listings")
    args = parser.parse_args()
    _ = args

    db = SessionLocal()
    try:
        grouped = collect_hybrid_models(db)
    finally:
        db.close()

    for engine_type in (HYBRID_TYPE_LABEL, PLUGIN_HYBRID_TYPE_LABEL):
        print(engine_type + ":")
        entries = grouped.get(engine_type, [])
        if not entries:
            print("  —")
            continue
        for entry in entries:
            print(f"  {entry.make} · {entry.model}")
        print()


if __name__ == "__main__":
    main()
