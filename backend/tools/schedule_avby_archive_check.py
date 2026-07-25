"""Run nightly archive check for listings removed from av.by."""

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

ARCHIVER_PATH = ROOT_DIR / "tools" / "archive_removed_avby_listings.py"
logger = logging.getLogger(__name__)


def run_once(delay_seconds: float) -> int:
    cmd = [sys.executable, str(ARCHIVER_PATH), "--delay", str(delay_seconds)]
    logger.info("archive-run-start: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
    if result.stdout:
        for line in result.stdout.splitlines()[-30:]:
            logger.info("archiver | %s", line)
    if result.stderr:
        for line in result.stderr.splitlines()[-20:]:
            logger.warning("archiver ! %s", line)
    logger.info("archive-run-finish: exit_code=%s", result.returncode)
    return result.returncode


def main() -> None:
    setup_logging("avby-archive")
    parser = argparse.ArgumentParser(description="Schedule nightly av.by archive check")
    parser.add_argument("--run-at-hour", type=int, default=3, help="Local hour to run (0-23)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between listing checks")
    parser.add_argument("--run-once", action="store_true", help="Run once and exit")
    args = parser.parse_args()

    run_hour = max(0, min(23, args.run_at_hour))

    if args.run_once:
        raise SystemExit(run_once(args.delay))

    last_run_date: str | None = None
    while True:
        now = datetime.now()
        today = now.date().isoformat()
        if now.hour == run_hour and last_run_date != today:
            run_once(args.delay)
            last_run_date = today
        elif now.hour != run_hour:
            last_run_date = None
        time.sleep(60)


if __name__ == "__main__":
    main()
