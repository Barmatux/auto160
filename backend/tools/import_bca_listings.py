"""Load parsed BCA lots from a JSON export into the app database."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.bca_admin import upsert_parsed_lots
from app.db import SessionLocal


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: import_bca_listings.py listings.json")
    items = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        saved = upsert_parsed_lots(db, items)
        db.commit()
        print("saved", saved)
    finally:
        db.close()


if __name__ == "__main__":
    main()
