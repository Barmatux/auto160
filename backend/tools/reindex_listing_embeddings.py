#!/usr/bin/env python3
"""Backfill / refresh listing embeddings in Auto160 Postgres (pgvector).

Examples:

  python tools/reindex_listing_embeddings.py --limit 50
  python tools/reindex_listing_embeddings.py --force
  python tools/reindex_listing_embeddings.py --ids 1,2,3
"""

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
from app.listing_embeddings import reindex_listings
from app.logging_setup import setup_logging


def main() -> int:
    setup_logging("listing-embeddings")
    parser = argparse.ArgumentParser(description="Reindex published listing embeddings")
    parser.add_argument("--limit", type=int, default=0, help="Max listings to scan (0 = all published)")
    parser.add_argument("--force", action="store_true", help="Re-embed even if content_hash matches")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--ids", default="", help="Comma-separated listing ids")
    args = parser.parse_args()

    listing_ids: list[int] | None = None
    if args.ids.strip():
        listing_ids = [int(part.strip()) for part in args.ids.split(",") if part.strip()]

    db = SessionLocal()
    try:
        stats = reindex_listings(
            db,
            listing_ids=listing_ids,
            limit=args.limit,
            force=args.force,
            batch_size=max(1, args.batch_size),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(
        "done scanned={scanned} embedded={embedded} skipped={skipped} deleted_stale={deleted_stale}".format(
            **stats
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
