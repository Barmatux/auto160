#!/usr/bin/env python3
"""Backfill / refresh rag_chunks (guides/FAQ) embeddings.

Examples:

  python tools/reindex_rag.py
  python tools/reindex_rag.py --force
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
from app.logging_setup import setup_logging
from app.rag import reindex_rag_chunks


def main() -> int:
    setup_logging("rag-reindex")
    parser = argparse.ArgumentParser(description="Reindex RAG guide/FAQ chunks")
    parser.add_argument("--force", action="store_true", help="Re-embed even if content_hash matches")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = reindex_rag_chunks(db, force=args.force)
        print(stats)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
