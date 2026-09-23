#!/usr/bin/env python3
"""Nightly schedule: customs import-date backfill for listings that already have a VIN."""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.logging_setup import setup_logging

IMPORTER_PATH = ROOT_DIR / "tools" / "backfill_customs_import_dates.py"
logger = logging.getLogger(__name__)


def run_once(*, delay: float, limit: int, force: bool, only_missing_date: bool) -> int:
    cmd = [
        sys.executable,
        str(IMPORTER_PATH),
        "--delay",
        str(delay),
    ]
    if limit and limit > 0:
        cmd.extend(["--limit", str(limit)])
    if force:
        cmd.append("--force")
    if only_missing_date:
        cmd.append("--only-missing-date")

    logger.info("customs-import-dates-start: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.splitlines()[-60:]:
            logger.info("customs-import | %s", line)
    if result.stderr:
        for line in result.stderr.splitlines()[-20:]:
            logger.warning("customs-import ! %s", line)
    logger.info("customs-import-dates-finish: exit_code=%s", result.returncode)
    return result.returncode


def main() -> None:
    setup_logging("customs-import-dates")
    parser = argparse.ArgumentParser(description="Schedule nightly customs import-date backfill")
    parser.add_argument("--run-at-hour", type=int, default=2, help="Local hour to run (0-23)")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between GTK requests")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max unique VINs per night (0 = all due candidates)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore cache TTL (use carefully — hits GTK for every VIN)",
    )
    parser.add_argument(
        "--only-missing-date",
        action="store_true",
        help="Focus on VINs without a stored release_date",
    )
    parser.add_argument("--run-once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    run_hour = max(0, min(23, args.run_at_hour))

    if args.run_once:
        raise SystemExit(
            run_once(
                delay=args.delay,
                limit=args.limit,
                force=args.force,
                only_missing_date=args.only_missing_date,
            )
        )

    last_run_date: str | None = None
    while True:
        now = datetime.now()
        today = now.date().isoformat()
        if now.hour == run_hour and last_run_date != today:
            run_once(
                delay=args.delay,
                limit=args.limit,
                force=args.force,
                only_missing_date=args.only_missing_date,
            )
            last_run_date = today
        elif now.hour != run_hour:
            last_run_date = None
        time.sleep(60)


if __name__ == "__main__":
    main()
