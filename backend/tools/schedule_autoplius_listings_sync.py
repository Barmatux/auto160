#!/usr/bin/env python3
"""Periodically import Autoplius listings from scrape-platform Postgres into Auto160."""

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

IMPORTER_PATH = ROOT_DIR / "tools" / "import_autoplius_listings.py"
logger = logging.getLogger(__name__)


def run_once(*, max_hp: int, max_age_years: int, max_engine_l: float) -> int:
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
    logger.info("autoplius-import-start: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.splitlines()[-40:]:
            logger.info("autoplius-import | %s", line)
    if result.stderr:
        for line in result.stderr.splitlines()[-20:]:
            logger.warning("autoplius-import ! %s", line)
    logger.info("autoplius-import-finish: exit_code=%s", result.returncode)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule Autoplius → Auto160 import")
    parser.add_argument("--interval-minutes", type=int, default=45)
    parser.add_argument("--max-hp", type=int, default=160)
    parser.add_argument("--max-age-years", type=int, default=5)
    parser.add_argument("--max-engine-l", type=float, default=1.9)
    parser.add_argument("--run-once", action="store_true")
    args = parser.parse_args()

    setup_logging()
    if args.run_once:
        return run_once(
            max_hp=args.max_hp,
            max_age_years=args.max_age_years,
            max_engine_l=args.max_engine_l,
        )

    interval_seconds = max(60, args.interval_minutes * 60)
    while True:
        run_once(
            max_hp=args.max_hp,
            max_age_years=args.max_age_years,
            max_engine_l=args.max_engine_l,
        )
        logger.info("sleep: %ss", interval_seconds)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
