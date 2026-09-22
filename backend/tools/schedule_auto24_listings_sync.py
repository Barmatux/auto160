#!/usr/bin/env python3
"""Periodically import Auto24 listings from scrape-platform Postgres into Auto160."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.logging_setup import setup_logging

IMPORTER_PATH = ROOT_DIR / "tools" / "import_auto24_listings.py"
REINDEX_PATH = ROOT_DIR / "tools" / "reindex_listing_embeddings.py"
logger = logging.getLogger(__name__)


def run_embedding_reindex() -> int:
    cmd = [sys.executable, str(REINDEX_PATH)]
    logger.info("auto24-embeddings-start: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.splitlines()[-20:]:
            logger.info("auto24-embeddings | %s", line)
    if result.stderr:
        for line in result.stderr.splitlines()[-10:]:
            logger.warning("auto24-embeddings ! %s", line)
    if result.returncode != 0:
        logger.warning("auto24-embeddings failed exit_code=%s; continuing", result.returncode)
        return 0
    logger.info("auto24-embeddings-finish: exit_code=%s", result.returncode)
    return 0


def run_once(
    *,
    max_hp: int,
    max_age_years: int,
    max_engine_l: float,
    reindex_embeddings: bool = False,
) -> int:
    cmd = [
        sys.executable,
        str(IMPORTER_PATH),
        "--max-hp",
        str(max_hp),
        "--max-age-years",
        str(max_age_years),
        "--max-engine-l",
        str(max_engine_l),
    ]
    logger.info("auto24-import-start: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.splitlines()[-40:]:
            logger.info("auto24-import | %s", line)
    if result.stderr:
        for line in result.stderr.splitlines()[-20:]:
            logger.warning("auto24-import ! %s", line)
    logger.info("auto24-import-finish: exit_code=%s", result.returncode)
    if result.returncode != 0:
        return result.returncode
    if reindex_embeddings:
        return run_embedding_reindex()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule Auto24 → Auto160 import")
    parser.add_argument("--interval-minutes", type=int, default=45)
    parser.add_argument("--max-hp", type=int, default=160)
    parser.add_argument("--max-age-years", type=int, default=5)
    parser.add_argument("--max-engine-l", type=float, default=1.9)
    parser.add_argument("--run-once", action="store_true")
    parser.add_argument(
        "--reindex-embeddings",
        action="store_true",
        help="Reindex listing embeddings after import (default: skip; use nightly listing-embeddings)",
    )
    args = parser.parse_args()

    setup_logging("auto24-sync")
    if args.run_once:
        return run_once(
            max_hp=args.max_hp,
            max_age_years=args.max_age_years,
            max_engine_l=args.max_engine_l,
            reindex_embeddings=args.reindex_embeddings,
        )

    interval_seconds = max(60, args.interval_minutes * 60)
    while True:
        run_once(
            max_hp=args.max_hp,
            max_age_years=args.max_age_years,
            max_engine_l=args.max_engine_l,
            reindex_embeddings=args.reindex_embeddings,
        )
        logger.info("sleep: %ss", interval_seconds)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
